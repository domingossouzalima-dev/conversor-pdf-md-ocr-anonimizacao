#!/usr/bin/env python3
"""
pdf_to_md.py — Converte um PDF em Markdown, marcando a página de origem
de cada bloco de texto com um cabeçalho "## Página N".

Copyright (c) 2026 domingossouzalima-dev
Licenciado sob a licença MIT. Veja o arquivo LICENSE na raiz do
repositório para o texto completo.

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
import sys
from pathlib import Path

MIN_CHARS_TEXTO_NATIVO = 25  # abaixo disso, consideramos a página "sem texto útil" -> OCR


def extrair_texto_nativo(pagina):
    try:
        texto = pagina.extract_text() or ""
    except Exception:
        texto = ""
    return texto.strip()


def ocr_pagina(caminho_pdf, numero_pagina, idioma):
    """Renderiza uma única página do PDF como imagem e roda OCR nela."""
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
    texto = pytesseract.image_to_string(imagens[0], lang=idioma)
    return texto.strip()


def converter_pdf(caminho_pdf: Path, caminho_saida: Path, forcar_ocr: bool, idioma: str, verbose=True):
    from pypdf import PdfReader

    leitor = PdfReader(str(caminho_pdf))
    total_paginas = len(leitor.pages)

    blocos = []
    paginas_com_ocr = []

    for i, pagina in enumerate(leitor.pages, start=1):
        texto = "" if forcar_ocr else extrair_texto_nativo(pagina)

        usado_ocr = False
        if len(texto) < MIN_CHARS_TEXTO_NATIVO:
            try:
                texto_ocr = ocr_pagina(caminho_pdf, i, idioma)
                if len(texto_ocr) > len(texto):
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
