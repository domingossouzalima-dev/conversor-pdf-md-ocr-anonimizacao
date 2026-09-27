#!/usr/bin/env python3
"""
pdf_to_md.py — Converte um PDF em Markdown, marcando a página de origem
de cada bloco de texto com um cabeçalho "## Página N".

Copyright (C) 2026 Domingos José de Souza Lima Júnior
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.
You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.

Uso:
    python3 pdf_to_md.py arquivo.pdf
    python3 pdf_to_md.py arquivo.pdf -o saida.md
    python3 pdf_to_md.py *.pdf              # converte vários de uma vez
    python3 pdf_to_md.py arquivo.pdf --forcar-ocr   # ignora texto nativo e usa OCR em tudo
    python3 pdf_to_md.py arquivo.pdf --idioma eng   # OCR em inglês (padrão: por = português)

Lógica:
    1. Para cada página, tenta extrair o texto nativo (PDF digital) com pypdf.
    2. Se o texto extraído for muito curto (ex.: página escaneada = imagem),
       a página é convertida em imagem e passada pelo Tesseract OCR.
    3. Cada página vira um bloco:

         ## Página 12

         (texto da página aqui...)

    4. Tudo é salvo em um único arquivo .md, com o mesmo nome do PDF.

Dependências (ver LEIA-ME.md para instruções passo a passo):
    pip install pypdf pdf2image pytesseract pillow
    + Tesseract OCR instalado no sistema (pacote `tesseract-ocr` e
      `tesseract-ocr-por` para português)
    + Poppler instalado no sistema (pacote `poppler-utils`), exigido pelo pdf2image
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from PIL import Image, ImageDraw

MIN_CHARS_TEXTO_NATIVO = 25  # abaixo disso, consideramos a página "sem texto útil" -> OCR

RE_TARJA_TRIBUNAL = re.compile(
    r"(?:Este documento é cópia do original assinado digitalmente|"
    r"Para conferir o original, acesse o site|"
    r"assinado digitalmente por|"
    r"Documento assinado eletronicamente|"
    r"Assinado eletronicamente por|"
    r"fls\.\s*\d+|"
    r"Num\.\s*\d+\s*-\s*Pág|"
    r"código\s+[0-9A-Za-z]{6,})",
    re.IGNORECASE
)


def pagina_precisa_ocr(texto_nativo: str, tem_imagens: bool = True) -> bool:
    """Avalia se uma página precisa de OCR, descontando tarjas vetoriais forenses (SAJ/PJe)."""
    if not texto_nativo:
        return True
    linhas_sem_tarja = [
        l for l in texto_nativo.splitlines() 
        if not RE_TARJA_TRIBUNAL.search(l)
    ]
    texto_util = " ".join(linhas_sem_tarja).strip()
    chars_alfanumericos = re.sub(r"\W+", "", texto_util)
    if len(chars_alfanumericos) < MIN_CHARS_TEXTO_NATIVO:
        return True
    return False


def mascarar_bordas_carimbo(imagem: Image.Image) -> Image.Image:
    """Mascara margens laterais onde residem tarjas verticais do e-SAJ (borda direita a partir de 93%)."""
    w, h = imagem.size
    x_direita = int(w * 0.930)
    draw = ImageDraw.Draw(imagem)
    draw.rectangle([x_direita, 0, w, h], fill="white")
    return imagem


def remover_linhas_tabela(imagem_bin: Image.Image) -> Image.Image:
    """Remove linhas horizontais finas (réguas de formulários e tabelas) que causam alucinações no OCR."""
    img = imagem_bin.copy()
    w, h = img.size
    pix = img.load()
    for y in range(2, h - 2):
        consecutivos = 0
        for x in range(w):
            if pix[x, y] == 0:
                consecutivos += 1
            else:
                if consecutivos > 80:
                    for xl in range(x - consecutivos, x):
                        if pix[xl, y - 2] == 255 and pix[xl, y + 2] == 255:
                            pix[xl, y] = 255
                            pix[xl, y - 1] = 255
                            pix[xl, y + 1] = 255
                consecutivos = 0
    return img


def eh_linha_ruido(linha: str) -> bool:
    """Detecta linhas espúrias formadas por traços divisórios, réguas ou ruído gráfico no OCR."""
    s = linha.strip()
    if not s:
        return False
    if re.match(r"^[\s\-_=—–+*~.:;,\'\"/\\|<>ºª§°¬!@#\$%\^&\[\]\(\)\{\}\?]+$", s):
        return True
    tokens = s.split()
    if not tokens:
        return False
    if len(tokens) >= 3 and all(len(t) <= 2 for t in tokens):
        if not re.search(r"\b(art|inc|lei|nº|no|fls|pág)\b", s, re.I):
            return True
    tokens_curtos = [t for t in tokens if len(t) <= 2]
    if len(tokens) >= 4 and len(tokens_curtos) / len(tokens) >= 0.8:
        if not re.search(r"\b(de|do|da|em|ao|às|no|na|art|lei)\b", s, re.I):
            return True
    return False


def limpar_ruido_ocr(texto: str) -> str:
    """Elimina blocos de linhas órfãs e artefatos de digitalização no Markdown."""
    linhas = texto.splitlines()
    linhas_filtradas = []
    i = 0
    n = len(linhas)
    while i < n:
        l = linhas[i].strip()
        if not l:
            linhas_filtradas.append(linhas[i])
            i += 1
            continue
        if eh_linha_ruido(l):
            i += 1
            continue
        if len(l) <= 3:
            j = i
            while j < n and (len(linhas[j].strip()) <= 3):
                j += 1
            orfas = [linhas[k].strip() for k in range(i, j) if linhas[k].strip()]
            if len(orfas) >= 3:
                i = j
                continue
            else:
                for k in range(i, j):
                    if not eh_linha_ruido(linhas[k]):
                        linhas_filtradas.append(linhas[k])
                i = j
        else:
            linhas_filtradas.append(linhas[i])
            i += 1

    texto_limpo = "\n".join(linhas_filtradas)
    texto_limpo = re.sub(r"\n{3,}", "\n\n", texto_limpo)
    return texto_limpo.strip()


def extrair_texto_nativo(pagina):
    try:
        texto = pagina.extract_text() or ""
    except Exception:
        texto = ""
    return texto.strip()


def ocr_pagina(caminho_pdf, numero_pagina, idioma):
    """Renderiza uma única página do PDF como imagem e roda OCR nela com máscara de borda e remoção de réguas."""
    from pdf2image import convert_from_path
    import pytesseract

    imagens = convert_from_path(
        caminho_pdf,
        dpi=300,
        first_page=numero_pagina,
        last_page=numero_pagina,
    )
    if not imagens:
        return ""
    img = mascarar_bordas_carimbo(imagens[0]).convert("L")
    threshold = 175
    bin_img = img.point(lambda p: 255 if p > threshold else 0)
    bin_img = remover_linhas_tabela(bin_img)
    config_tess = "--psm 3 -c preserve_interword_spaces=1"
    texto = pytesseract.image_to_string(bin_img, lang=idioma, config=config_tess)
    return limpar_ruido_ocr(texto.strip())


def _obter_executavel_ocrmypdf():
    """Detecta o executável do OCRmyPDF no PATH, via Snap, ou como módulo Python."""
    bin_path = shutil.which("ocrmypdf")
    if bin_path:
        return [bin_path]
    if sys.platform != "win32" and Path("/snap/bin/ocrmypdf").exists():
        return ["/snap/bin/ocrmypdf"]
    try:
        res = subprocess.run(
            [sys.executable, "-m", "ocrmypdf", "--version"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if res.returncode == 0:
            return [sys.executable, "-m", "ocrmypdf"]
    except Exception:
        pass
    return None


def _pre_processar_com_ocrmypdf(caminho_pdf: Path, pdf_saida: Path, idioma: str, forcar_ocr: bool, verbose=True) -> bool:
    """
    Pré-processa o PDF com OCRmyPDF (deskew + rotação automática + limpeza
    de ruído) antes da extração de texto. Sem isso, o OCR de fallback
    (Tesseract cru, sem pré-processamento) falha silenciosamente ou produz
    texto incompleto em páginas escaneadas tortas/rotacionadas/ruidosas —
    exatamente o cenário de "várias páginas deram erro" em BOs e autos
    policiais fotocopiados/escaneados em lote.

    forcar_ocr=False usa --skip-text (modo híbrido: preserva texto nativo
    já bom, só aplica deskew/limpeza + OCR nas páginas sem texto) —
    apropriado para o uso normal deste script (padrão/anonimização).
    forcar_ocr=True usa --force-ocr (reprocessa tudo via OCR).
    """
    cmd_base = _obter_executavel_ocrmypdf()
    if not cmd_base:
        return False
    workers = str(min(4, os.cpu_count() or 1))
    cmd = cmd_base + [
        "-l", idioma,
        "--rotate-pages",
        "--deskew",
        "--clean",
        "--invalidate-digital-signatures",
        "--force-ocr" if forcar_ocr else "--skip-text",
        "--jobs", workers,
        str(caminho_pdf),
        str(pdf_saida),
    ]
    if verbose:
        print("  Pré-processando com OCRmyPDF (rotação, deskew, limpeza de ruído)...")
    try:
        resultado = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if resultado.returncode == 0 and pdf_saida.exists() and pdf_saida.stat().st_size > 0:
            return True
        if verbose:
            erro_resumo = (resultado.stderr or "").strip()[-200:]
            print(f"  [aviso] OCRmyPDF retornou código {resultado.returncode}. Motivo: {erro_resumo}. Usando fallback página a página.", file=sys.stderr)
        return False
    except Exception as e:
        if verbose:
            print(f"  [aviso] Falha ao executar OCRmyPDF: {e}. Usando fallback página a página.", file=sys.stderr)
        return False


def converter_pdf(caminho_pdf: Path, caminho_saida: Path, forcar_ocr: bool, idioma: str, verbose=True):
    from pypdf import PdfReader

    leitor = PdfReader(str(caminho_pdf))
    total_paginas = len(leitor.pages)

    # Identifica quais páginas não têm texto nativo útil (descontando tarjas de tribunais).
    paginas_sem_texto_nativo = set()
    if not forcar_ocr:
        for i, pagina in enumerate(leitor.pages, start=1):
            t_nat = extrair_texto_nativo(pagina)
            tem_imgs = hasattr(pagina, "images") and len(pagina.images) > 0
            if pagina_precisa_ocr(t_nat, tem_imgs):
                paginas_sem_texto_nativo.add(i)

    tmp_dir = Path(tempfile.mkdtemp(prefix="pdf_to_md_ocrmypdf_"))
    pdf_temp = tmp_dir / f"processado_{int(time.time() * 1000)}.pdf"
    sucesso_ocrmypdf = False
    try:
        sucesso_ocrmypdf = _pre_processar_com_ocrmypdf(caminho_pdf, pdf_temp, idioma, forcar_ocr, verbose=verbose)
        if sucesso_ocrmypdf:
            leitor = PdfReader(str(pdf_temp))
            total_paginas = len(leitor.pages)

        blocos = []
        paginas_com_ocr = []

        for i, pagina in enumerate(leitor.pages, start=1):
            usado_ocr = False

            if sucesso_ocrmypdf:
                texto = extrair_texto_nativo(pagina)
                if forcar_ocr or i in paginas_sem_texto_nativo:
                    usado_ocr = True
            else:
                texto_nativo = extrair_texto_nativo(pagina)
                tem_imgs = hasattr(pagina, "images") and len(pagina.images) > 0
                precisa = pagina_precisa_ocr(texto_nativo, tem_imgs)
                if forcar_ocr:
                    linhas_sem_tarja = [l for l in texto_nativo.splitlines() if not RE_TARJA_TRIBUNAL.search(l)]
                    chars_uteis = len(re.sub(r"\W+", "", " ".join(linhas_sem_tarja)))
                    executar_ocr = precisa or chars_uteis < 150
                else:
                    executar_ocr = precisa

                texto = texto_nativo
                if executar_ocr:
                    try:
                        texto_ocr = ocr_pagina(caminho_pdf, i, idioma)
                        if texto_ocr:
                            texto = texto_ocr
                            usado_ocr = True
                    except Exception as e:
                        if verbose:
                            print(f"  [aviso] OCR falhou na página {i}: {e}", file=sys.stderr)

            if usado_ocr:
                paginas_com_ocr.append(i)

            if not texto:
                texto = "*(nenhum texto extraído nesta página)*"

            blocos.append(f"## Página {i}\n\n{texto}\n")

            if verbose:
                marca = "OCR" if usado_ocr else "texto nativo"
                print(f"  página {i}/{total_paginas} ({marca}) — {len(texto)} caracteres")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    cabecalho = f"<!-- Convertido de: {caminho_pdf.name} | {total_paginas} páginas -->\n\n"
    conteudo_final = cabecalho + "\n---\n\n".join(blocos)

    caminho_saida.write_text(conteudo_final, encoding="utf-8")

    if verbose:
        print(f"\n✔ Gerado: {caminho_saida}")
        if paginas_com_ocr:
            print(f"  Páginas que precisaram de OCR: {paginas_com_ocr}")


def main():
    parser = argparse.ArgumentParser(description="Converte PDF em Markdown com marcação de página.")
    parser.add_argument("pdfs", nargs="+", help="Um ou mais arquivos PDF de entrada")
    parser.add_argument("-o", "--saida", help="Caminho do .md de saída (só válido com um único PDF de entrada)")
    parser.add_argument("--forcar-ocr", action="store_true", help="Ignora o texto nativo e usa OCR em todas as páginas")
    parser.add_argument("--idioma", default="por", help="Idioma do OCR no formato do Tesseract (padrão: por)")
    args = parser.parse_args()

    if args.saida and len(args.pdfs) > 1:
        print("Erro: -o/--saida só pode ser usado com um único PDF de entrada.", file=sys.stderr)
        sys.exit(1)

    for caminho_str in args.pdfs:
        caminho_pdf = Path(caminho_str)
        if not caminho_pdf.exists():
            print(f"Erro: arquivo não encontrado: {caminho_pdf}", file=sys.stderr)
            continue

        caminho_saida = Path(args.saida) if args.saida else caminho_pdf.with_suffix(".md")

        print(f"Convertendo: {caminho_pdf.name}")
        converter_pdf(caminho_pdf, caminho_saida, args.forcar_ocr, args.idioma)
        print()


if __name__ == "__main__":
    main()
