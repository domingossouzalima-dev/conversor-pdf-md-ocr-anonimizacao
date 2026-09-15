#!/usr/bin/env python3
"""
auto_conversor.py — Sistema Automatizado de Conversão de Documentos (PDF/Imagens para Markdown)
com Rastreabilidade e Suporte a OCR e Anonimização Forense (Res. CNJ nº 615/2025).

Copyright (c) 2026 domingossouzalima-dev
Licenciado sob a licença MIT. Veja o arquivo LICENSE na raiz do repositório.

ESTRUTURA DE DIRETÓRIOS OPERADOS (caminhos relativos à raiz do repositório):
  Entrada:
    - arquivos_de_entrada/padrao/          -> Conversão com texto nativo e fallback OCR
    - arquivos_de_entrada/ocr/             -> Conversão com OCR FORÇADO em todas as páginas
    - arquivos_de_entrada/anonimizacao/    -> Conversão com anonimização (Res. CNJ 615/2025)
    - arquivos_de_entrada/desanonimizacao/ -> Reversão: solte aqui o documento anonimizado
                                               junto com sua respectiva chave (arquivo
                                               "chave_de_desanonimizacao_*.md"); o script
                                               casa os dois sozinho pelo nome/código de
                                               referência, mesmo com vários pares juntos.

  Saída:
    - arquivos_convertidos/padrao/AAAA-MM-DD/
    - arquivos_convertidos/ocr/AAAA-MM-DD/
    - arquivos_convertidos/anonimizacao/AAAA-MM-DD/
    - arquivos_convertidos/desanonimizacao/AAAA-MM-DD/<nome>/
        -> pasta por documento, contendo: o documento anonimizado original,
           a chave usada e o "desanonimizado_*.md" já revertido/preenchido.

  Ao concluir a conversão:
    1. O arquivo original é transportado (movido) para a subpasta da data correspondente.
    2. O arquivo .md resultante é gerado dentro da mesma subpasta da data.
    3. O arquivo .md contém metadados completos de rastreabilidade (nome original, hash, data, páginas e páginas com OCR).

USO:
    python3 auto_conversor.py                 # Processa uma vez todos os arquivos pendentes na fila
    python3 auto_conversor.py --watch         # Modo vigilância contínua (monitora em tempo real)
    python3 auto_conversor.py --status        # Exibe status das pastas de entrada e saída
"""

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from PIL import Image
import pytesseract

# Importação condicional de motores PDF de alta performance
try:
    import pymupdf as fitz
    TEM_PYMUPDF = True
except ImportError:
    try:
        import fitz
        TEM_PYMUPDF = True
    except ImportError:
        TEM_PYMUPDF = False

try:
    from pypdf import PdfReader
    TEM_PYPDF = True
except ImportError:
    TEM_PYPDF = False

try:
    from pdf2image import convert_from_path
    TEM_PDF2IMAGE = True
except ImportError:
    TEM_PDF2IMAGE = False

# Diretórios base dinâmicos (compatíveis com Linux e Windows)
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent  # raiz do repositório
ENTRADA_DIR = BASE_DIR / "arquivos_de_entrada"
SAIDA_DIR = BASE_DIR / "arquivos_convertidos"
LOG_DIR = BASE_DIR / "log"
TMP_OCR_DIR = BASE_DIR / ".tmp_ocr"

# Detecção automática do executável Tesseract no Windows se não estiver no PATH
if sys.platform == "win32":
    caminhos_tesseract_win = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tesseract-OCR" / "tesseract.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Tesseract-OCR" / "tesseract.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Tesseract-OCR" / "tesseract.exe",
    ]
    for p_tess in caminhos_tesseract_win:
        if p_tess.exists():
            pytesseract.pytesseract.tesseract_cmd = str(p_tess)
            break


def obter_executavel_ocrmypdf() -> list[str] | None:
    """Detecta o executável do OCRmyPDF no Linux (PATH/Snap) ou Windows (PATH/Python module)."""
    # 1. Checa se o comando está no PATH do sistema
    bin_path = shutil.which("ocrmypdf")
    if bin_path:
        return [bin_path]
    # 2. No Linux, checa instalação via Snap (/snap/bin/ocrmypdf)
    if sys.platform != "win32" and Path("/snap/bin/ocrmypdf").exists():
        return ["/snap/bin/ocrmypdf"]
    # 3. Testa invocação via módulo python (python -m ocrmypdf)
    try:
        res = subprocess.run(
            [sys.executable, "-m", "ocrmypdf", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if res.returncode == 0:
            return [sys.executable, "-m", "ocrmypdf"]
    except Exception:
        pass
    return None


MODOS = {
    "padrao": {
        "entrada": ENTRADA_DIR / "padrao",
        "saida": SAIDA_DIR / "padrao",
        "descricao": "Padrão (Texto Nativo com OCR automático em páginas escaneadas)",
        "forcar_ocr": False,
        "anonimizar": False,
    },
    "ocr": {
        "entrada": ENTRADA_DIR / "ocr",
        "saida": SAIDA_DIR / "ocr",
        "descricao": "OCR Otimizado (Estratégia 2: OCRmyPDF com Deskew, Rotação e Limpeza; Fallback 300 DPI)",
        "forcar_ocr": True,
        "anonimizar": False,
    },
    "anonimizacao": {
        "entrada": ENTRADA_DIR / "anonimizacao",
        "saida": SAIDA_DIR / "anonimizacao",
        "descricao": "Anonimização Forense (Resolução CNJ nº 615/2025)",
        "forcar_ocr": False,
        "anonimizar": True,
    },
    "desanonimizacao": {
        "entrada": ENTRADA_DIR / "desanonimizacao",
        "saida": SAIDA_DIR / "desanonimizacao",
        "descricao": "Desanonimização (reverte um documento anonimizado usando sua chave)",
        "forcar_ocr": False,
        "anonimizar": False,
    },
}

MIN_CHARS_TEXTO_NATIVO = 25
EXTENSOES_SUPORTADAS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}

# Prefixo que identifica um arquivo de chave de desanonimização pelo nome.
PREFIXO_CHAVE = "chave_de_desanonimizacao_"
RE_REF_CODE = re.compile(r"ref-([0-9a-f]{6})", re.IGNORECASE)
RE_LINHA_CHAVE = re.compile(r"^(\S+) → (.*)$", re.MULTILINE)


def calcular_sha256(caminho: Path) -> str:
    """Calcula hash SHA-256 do arquivo para integridade e rastreabilidade."""
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def arquivo_estavel(caminho: Path, espera: float = 0.5) -> bool:
    """Verifica se o arquivo terminou de ser gravado no disco antes de processar."""
    try:
        tamanho_1 = caminho.stat().st_size
        time.sleep(espera)
        tamanho_2 = caminho.stat().st_size
        return tamanho_1 == tamanho_2 and tamanho_1 > 0
    except (FileNotFoundError, PermissionError):
        return False


def obter_destino_unico(pasta_destino: Path, nome_arquivo: str) -> Path:
    """Evita sobrescrita de arquivos caso já exista arquivo com mesmo nome no destino."""
    destino = pasta_destino / nome_arquivo
    if not destino.exists():
        return destino
    stem = destino.stem
    suffix = destino.suffix
    contador = 1
    while destino.exists():
        destino = pasta_destino / f"{stem}_{contador}{suffix}"
        contador += 1
    return destino


def ocr_imagem_pil(imagem: Image.Image, idioma: str = "por") -> str:
    """Executa OCR sobre um objeto PIL Image."""
    try:
        texto = pytesseract.image_to_string(imagem, lang=idioma)
        return texto.strip()
    except Exception as e:
        print(f"    [erro ocr] Falha no Tesseract: {e}", file=sys.stderr)
        return ""


def processar_pagina_pymupdf(doc, i: int, forcar_ocr: bool, idioma: str = "por") -> tuple[str, bool]:
    """Extrai texto da página via PyMuPDF com renderização de imagem para OCR."""
    pagina = doc[i]
    texto = ""
    usou_ocr = False

    if not forcar_ocr:
        texto = pagina.get_text("text").strip()

    if forcar_ocr or len(texto) < MIN_CHARS_TEXTO_NATIVO:
        try:
            # Renderização com matriz 300 DPI (300 / 72 ≈ 4.166)
            zoom = 300 / 72
            matriz = fitz.Matrix(zoom, zoom)
            pix = pagina.get_pixmap(matrix=matriz, alpha=False)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            texto_ocr = ocr_imagem_pil(img, idioma)
            if forcar_ocr or len(texto_ocr) > len(texto):
                texto = texto_ocr
                usou_ocr = True
        except Exception as e:
            print(f"    [aviso] Falha ao renderizar página {i+1} no PyMuPDF: {e}", file=sys.stderr)

    return texto, usou_ocr


def processar_pagina_fallback(caminho_pdf: Path, i: int, leitor_pypdf, forcar_ocr: bool, idioma: str = "por") -> tuple[str, bool]:
    """Fallback usando pypdf e pdf2image caso PyMuPDF não esteja disponível."""
    texto = ""
    usou_ocr = False
    pagina = leitor_pypdf.pages[i]

    if not forcar_ocr:
        try:
            texto = (pagina.extract_text() or "").strip()
        except Exception:
            texto = ""

    if forcar_ocr or len(texto) < MIN_CHARS_TEXTO_NATIVO:
        if TEM_PDF2IMAGE:
            try:
                imagens = convert_from_path(str(caminho_pdf), dpi=300, first_page=i+1, last_page=i+1)
                if imagens:
                    texto_ocr = ocr_imagem_pil(imagens[0], idioma)
                    if forcar_ocr or len(texto_ocr) > len(texto):
                        texto = texto_ocr
                        usou_ocr = True
            except Exception as e:
                print(f"    [aviso] Falha no fallback pdf2image na página {i+1}: {e}", file=sys.stderr)

    return texto, usou_ocr


def formatar_segundos(s: float) -> str:
    """Formata segundos em formato legível (ex.: 02m 45s ou 01h 10m 20s)."""
    s_int = max(0, int(s))
    m = s_int // 60
    seg = s_int % 60
    if m >= 60:
        h = m // 60
        m = m % 60
        return f"{h:02d}h {m:02d}m {seg:02d}s"
    return f"{m:02d}m {seg:02d}s"


def atualizar_progresso(
    nome_arquivo: str,
    modo: str,
    pag_atual: int,
    total_pags: int,
    pags_ocr: int,
    t_inicio: float,
    fase: str = "",
):
    """Atualiza progresso no terminal e em log/progresso.json."""
    porcentagem = (pag_atual / total_pags) * 100 if total_pags > 0 else 0
    t_decorrido = time.time() - t_inicio
    if pag_atual > 0:
        tempo_por_pag = t_decorrido / pag_atual
        tempo_restante_s = tempo_por_pag * (total_pags - pag_atual)
        restante_str = formatar_segundos(tempo_restante_s)
    else:
        restante_str = "calculando..."

    decorrido_str = formatar_segundos(t_decorrido)
    info_fase = f" | Fase: {fase}" if fase else ""
    linha_status = (
        f"[{modo.upper()}] '{nome_arquivo}' | Página {pag_atual}/{total_pags} ({porcentagem:.1f}%)"
        f"{info_fase} | Decorrido: {decorrido_str} | Restante est.: ~{restante_str}"
    )

    # Imprime com flush imediato para aparecer no journalctl e terminal
    print(f"  {linha_status}", flush=True)

    dados = {
        "status": "processando",
        "arquivo": nome_arquivo,
        "modo": modo,
        "fase": fase or "Processamento padrão",
        "pagina_atual": pag_atual,
        "total_paginas": total_pags,
        "porcentagem": round(porcentagem, 1),
        "paginas_com_ocr": pags_ocr,
        "tempo_decorrido": decorrido_str,
        "tempo_restante_estimado": restante_str,
        "atualizado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        (LOG_DIR / "progresso.json").write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
        (LOG_DIR / "progresso.txt").write_text(linha_status + "\n", encoding="utf-8")
    except Exception:
        pass


def finalizar_progresso(nome_arquivo: str, total_pags: int, duracao_s: float, motor_usado: str = ""):
    """Marca o estado como ocioso após conclusão de conversão."""
    dados = {
        "status": "ocioso",
        "ultimo_arquivo": nome_arquivo,
        "motor_utilizado": motor_usado,
        "total_paginas": total_pags,
        "duracao_total": formatar_segundos(duracao_s),
        "concluido_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        (LOG_DIR / "progresso.json").write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
        (LOG_DIR / "progresso.txt").write_text(
            f"[OCIOSO] Nenhuma conversão ativa. Último concluído: '{nome_arquivo}' ({total_pags} páginas em {formatar_segundos(duracao_s)} às {dados['concluido_em']}).\n",
            encoding="utf-8",
        )
    except Exception:
        pass


def executar_ocrmypdf(
    caminho_entrada: Path,
    caminho_saida: Path,
    total_paginas: int,
    idioma: str = "por",
    nome_doc: str = "",
    t_inicio: float = None,
    forcar_ocr: bool = True,
) -> bool:
    """Executa o OCRmyPDF com deskew, rotação automática de páginas e limpeza profunda (Estratégia 2).

    forcar_ocr=True usa --force-ocr (reprocessa TODAS as páginas via OCR,
    descartando texto nativo existente) — usado no modo "ocr" dedicado.
    forcar_ocr=False usa --skip-text (modo híbrido: preserva o texto nativo
    das páginas que já têm texto e aplica deskew/rotação/limpeza + OCR
    apenas nas páginas sem texto) — usado nos modos "padrao" e
    "anonimizacao", que antes desta correção nunca chamavam o OCRmyPDF e
    caíam direto no fallback página a página sem deskew/limpeza, deixando
    passar páginas escaneadas tortas/ruidosas sem OCR efetivo.
    """
    cmd_base = obter_executavel_ocrmypdf()
    if not cmd_base:
        return False

    TMP_OCR_DIR.mkdir(parents=True, exist_ok=True)
    if t_inicio is None:
        t_inicio = time.time()

    cmd = cmd_base + [
        "-l", idioma,
        "--rotate-pages",
        "--deskew",
        "--clean",
        "--force-ocr" if forcar_ocr else "--skip-text",
        "--jobs", "0",
        str(caminho_entrada),
        str(caminho_saida),
    ]

    atualizar_progresso(
        nome_doc, "ocr", 0, total_paginas, 0, t_inicio,
        fase="OCRmyPDF: Rotação, Desinclinação (Deskew) e Limpeza"
    )

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        padrao_pag = re.compile(r"^\s*(\d+)\s+(?:page|\[tesseract\])")
        paginas_detectadas = set()

        for linha in proc.stdout:
            linha_limpa = linha.strip()
            if not linha_limpa:
                continue

            match = padrao_pag.search(linha_limpa)
            if match:
                pag_num = int(match.group(1))
                if 1 <= pag_num <= total_paginas:
                    paginas_detectadas.add(pag_num)
                    atualizar_progresso(
                        nome_doc, "ocr", len(paginas_detectadas), total_paginas, len(paginas_detectadas), t_inicio,
                        fase="OCRmyPDF: Processando páginas"
                    )

        proc.wait()
        if proc.returncode == 0 and caminho_saida.exists() and caminho_saida.stat().st_size > 0:
            return True
        else:
            print(f"    [aviso] OCRmyPDF retornou código {proc.returncode}. Ativando fallback...", file=sys.stderr)
            return False
    except Exception as e:
        print(f"    [aviso] Falha ao executar OCRmyPDF: {e}. Ativando fallback...", file=sys.stderr)
        return False


def converter_pdf_para_md(caminho_pdf: Path, forcar_ocr: bool = False, idioma: str = "por",
                          nome_arquivo: str = "", modo_chave: str = "", t_inicio: float = None) -> tuple[str, int, list[int], str]:
    """Converte PDF para blocos Markdown com suporte a OCRmyPDF (Estratégia 2) e fallback Tesseract 300 DPI."""
    if t_inicio is None:
        t_inicio = time.time()
    nome_doc = nome_arquivo or caminho_pdf.name
    modo_doc = modo_chave or ("ocr" if forcar_ocr else "padrao")

    paginas_ocr = []
    blocos = []
    total_paginas = 0

    # 1. Determina total de páginas
    if TEM_PYMUPDF:
        with fitz.open(str(caminho_pdf)) as d_tmp:
            total_paginas = len(d_tmp)
    elif TEM_PYPDF:
        leitor_tmp = PdfReader(str(caminho_pdf))
        total_paginas = len(leitor_tmp.pages)
    else:
        raise RuntimeError("Nenhum motor de leitura de PDF disponível (PyMuPDF ou pypdf necessários).")

    # 2. ESTRATÉGIA 2: Pré-processamento avançado com OCRmyPDF — SEMPRE que
    #    disponível, não apenas no modo "ocr" forçado. Nos modos "padrao" e
    #    "anonimizacao" (forcar_ocr=False) usa-se --skip-text (preserva
    #    texto nativo já bom, aplica deskew/rotação/limpeza + OCR só nas
    #    páginas sem texto). Sem isso, páginas escaneadas tortas ou com
    #    ruído nunca recebiam deskew/limpeza e o OCR de fallback (Tesseract
    #    puro, sem pré-processamento) falhava ou produzia texto incompleto
    #    nessas páginas — a causa raiz de páginas "em branco"/com erro e de
    #    dados pessoais não detectados pela anonimização (o motor de
    #    anonimização não consegue mascarar o que o OCR nunca extraiu).
    sucesso_ocrmypdf = False
    pdf_para_leitura = caminho_pdf
    pdf_temp_saida = None

    # Antes de reescrever o PDF, identifica quais páginas já têm texto
    # nativo suficiente — usado só para rotular corretamente (na saída)
    # quais páginas passaram por OCR quando o modo é híbrido (--skip-text),
    # já que nesse modo o OCRmyPDF não relata isso página a página.
    paginas_sem_texto_nativo = set()
    if not forcar_ocr:
        try:
            if TEM_PYMUPDF:
                with fitz.open(str(caminho_pdf)) as d_scan:
                    for j in range(len(d_scan)):
                        if len(d_scan[j].get_text("text").strip()) < MIN_CHARS_TEXTO_NATIVO:
                            paginas_sem_texto_nativo.add(j + 1)
            elif TEM_PYPDF:
                leitor_scan = PdfReader(str(caminho_pdf))
                for j, pag_scan in enumerate(leitor_scan.pages):
                    try:
                        texto_scan = (pag_scan.extract_text() or "").strip()
                    except Exception:
                        texto_scan = ""
                    if len(texto_scan) < MIN_CHARS_TEXTO_NATIVO:
                        paginas_sem_texto_nativo.add(j + 1)
        except Exception:
            pass

    if obter_executavel_ocrmypdf() is not None:
        TMP_OCR_DIR.mkdir(parents=True, exist_ok=True)
        timestamp_ms = int(time.time() * 1000)
        pdf_temp_saida = TMP_OCR_DIR / f"ocr_{timestamp_ms}_{caminho_pdf.name}"
        sucesso_ocrmypdf = executar_ocrmypdf(
            caminho_pdf,
            pdf_temp_saida,
            total_paginas=total_paginas,
            idioma=idioma,
            nome_doc=nome_doc,
            t_inicio=t_inicio,
            forcar_ocr=forcar_ocr,
        )
        if sucesso_ocrmypdf:
            pdf_para_leitura = pdf_temp_saida
            if forcar_ocr:
                motor_utilizado = "OCRmyPDF (Deskew, Rotação Automática, Limpeza de Ruído e OCR Forçado) [Estratégia 2]"
            else:
                motor_utilizado = "OCRmyPDF (Deskew, Rotação Automática, Limpeza de Ruído; OCR apenas em páginas sem texto) [Estratégia 2 Híbrida]"

    if not sucesso_ocrmypdf:
        if forcar_ocr:
            motor_utilizado = "PyMuPDF + Tesseract 300 DPI (Renderização página a página) [Estratégia 1 / Fallback]"
        else:
            motor_utilizado = "PyMuPDF (Texto Nativo com fallback OCR Tesseract em páginas escaneadas) [Fallback]"

    # 3. Extração estruturada do texto página a página
    try:
        if TEM_PYMUPDF:
            with fitz.open(str(pdf_para_leitura)) as doc:
                total_paginas = len(doc)
                atualizar_progresso(nome_doc, modo_doc, 0, total_paginas, 0, t_inicio, fase="Extraindo texto")
                for i in range(total_paginas):
                    if sucesso_ocrmypdf:
                        pagina = doc[i]
                        texto = pagina.get_text("text").strip()
                        num_pag = i + 1
                        if forcar_ocr or num_pag in paginas_sem_texto_nativo:
                            paginas_ocr.append(num_pag)
                            tag_tipo = " (OCR Otimizado - OCRmyPDF)"
                        else:
                            tag_tipo = ""
                    else:
                        texto, usou_ocr = processar_pagina_pymupdf(doc, i, forcar_ocr, idioma)
                        num_pag = i + 1
                        if usou_ocr:
                            paginas_ocr.append(num_pag)
                            tag_tipo = " (OCR)" if not forcar_ocr else " (OCR Forçado)"
                        else:
                            tag_tipo = ""

                    if not texto:
                        texto = "*(nenhum texto detectado nesta página)*"

                    blocos.append(f"## Página {num_pag}{tag_tipo}\n\n{texto}\n")
                    atualizar_progresso(
                        nome_doc, modo_doc, num_pag, total_paginas, len(paginas_ocr), t_inicio,
                        fase="Extraindo texto estruturado"
                    )
        elif TEM_PYPDF:
            leitor = PdfReader(str(pdf_para_leitura))
            total_paginas = len(leitor.pages)
            atualizar_progresso(nome_doc, modo_doc, 0, total_paginas, 0, t_inicio, fase="Extraindo texto")
            for i in range(total_paginas):
                if sucesso_ocrmypdf:
                    pagina = leitor.pages[i]
                    texto = (pagina.extract_text() or "").strip()
                    num_pag = i + 1
                    if forcar_ocr or num_pag in paginas_sem_texto_nativo:
                        paginas_ocr.append(num_pag)
                        tag_tipo = " (OCR Otimizado - OCRmyPDF)"
                    else:
                        tag_tipo = ""
                else:
                    texto, usou_ocr = processar_pagina_fallback(pdf_para_leitura, i, leitor, forcar_ocr, idioma)
                    num_pag = i + 1
                    if usou_ocr:
                        paginas_ocr.append(num_pag)
                        tag_tipo = " (OCR)"
                    else:
                        tag_tipo = ""

                if not texto:
                    texto = "*(nenhum texto detectado nesta página)*"

                blocos.append(f"## Página {num_pag}{tag_tipo}\n\n{texto}\n")
                atualizar_progresso(
                    nome_doc, modo_doc, num_pag, total_paginas, len(paginas_ocr), t_inicio,
                    fase="Extraindo texto estruturado"
                )
    finally:
        # Exclui o PDF temporário com segurança caso tenha sido gerado pelo OCRmyPDF
        if pdf_temp_saida and pdf_temp_saida.exists():
            try:
                pdf_temp_saida.unlink()
            except Exception:
                pass

    corpo_md = "\n---\n\n".join(blocos)
    return corpo_md, total_paginas, paginas_ocr, motor_utilizado


def converter_imagem_para_md(caminho_img: Path, idioma: str = "por") -> str:
    """Converte arquivo de imagem direta para Markdown via OCR."""
    img = Image.open(caminho_img)
    texto = ocr_imagem_pil(img, idioma)
    if not texto:
        texto = "*(nenhum texto legível detectado na imagem)*"
    return f"## Imagem Documental (OCR)\n\n{texto}\n"


RE_BLOCO_PAGINA = re.compile(r"^## Página (\d+)[^\n]*\n\n(.*)$", re.DOTALL)


def _iterar_blocos_paginas(corpo_md: str):
    """Percorre os blocos '## Página N ...' de um corpo já convertido,
    devolvendo (numero_pagina, texto_da_pagina) para cada um."""
    for bloco in corpo_md.split("\n---\n\n"):
        m = RE_BLOCO_PAGINA.match(bloco.strip("\n"))
        if not m:
            continue
        yield int(m.group(1)), m.group(2).rstrip("\n")


def anonimizar_conteudo(corpo_md: str, referencia: str) -> tuple[str, str]:
    """
    Aplica o motor de anonimização de pdf_to_md_anonimizado.py (CPF, CNPJ,
    processo, CEP, e-mail, telefone, RG, endereço, estado/município,
    tribunal e nomes de pessoas por heurística) sobre o corpo já convertido
    para Markdown, preservando a marcação "## Página N". Retorna
    (corpo_anonimizado, chave_de_desanonimizacao_em_markdown).
    """
    script_anonimizador = BASE_DIR / "scripts" / "pdf_to_md_anonimizado.py"
    if not script_anonimizador.exists():
        # Rede de segurança mínima caso o motor completo não esteja
        # disponível: só os padrões estruturados mais simples, sem chave
        # reversível (não há como desanonimizar esta saída depois).
        texto_anon = corpo_md
        texto_anon = re.sub(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", "[cpf_oculto]", texto_anon)
        texto_anon = re.sub(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b", "[cnpj_oculto]", texto_anon)
        texto_anon = re.sub(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b", "[processo_oculto]", texto_anon)
        chave = (
            "# Chave de Desanonimização\n\n"
            "*Aviso: o motor completo (pdf_to_md_anonimizado.py) não foi "
            "encontrado. Apenas padrões básicos foram aplicados, sem "
            "registro reversível — esta anonimização não pode ser "
            "desfeita automaticamente.*\n"
        )
        return texto_anon, chave

    import importlib.util
    spec = importlib.util.spec_from_file_location("pdf_to_md_anonimizado", script_anonimizador)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)

    motor = modulo.MotorAnonimizacao()
    blocos_anon = []
    total_paginas = 0
    for numero_pagina, texto_pagina in _iterar_blocos_paginas(corpo_md):
        total_paginas = max(total_paginas, numero_pagina)
        texto_anon = motor.processar_pagina(texto_pagina, numero_pagina)
        blocos_anon.append(f"## Página {numero_pagina}\n\n{texto_anon}\n")

    corpo_anonimizado = "\n---\n\n".join(blocos_anon)
    chave_md = motor.gerar_markdown_chave(referencia, total_paginas)
    return corpo_anonimizado, chave_md


def gravar_log(data_str: str, texto_log: str):
    """Grava entrada de log dentro da subpasta diária: log/AAAA-MM-DD/."""
    pasta_log_dia = LOG_DIR / data_str
    pasta_log_dia.mkdir(parents=True, exist_ok=True)
    arquivo_log = pasta_log_dia / f"conversoes_{data_str}.log"
    with open(arquivo_log, "a", encoding="utf-8") as f:
        f.write(texto_log + "\n")


def processar_arquivo(caminho_origem: Path, modo_chave: str):
    """Executa o pipeline completo de conversão, referência e transporte para a subpasta da data."""
    t_inicio = time.time()
    cfg = MODOS[modo_chave]
    nome_arquivo = caminho_origem.name
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    hora_agora = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")

    pasta_destino_dia = cfg["saida"] / data_hoje
    pasta_destino_dia.mkdir(parents=True, exist_ok=True)

    print(f"\n[{modo_chave.upper()}] Processando: {nome_arquivo}")

    # 1. Metadados e Hash
    hash_orig = calcular_sha256(caminho_origem)
    tamanho_bytes = caminho_origem.stat().st_size
    tamanho_legivel = f"{tamanho_bytes / 1024:.1f} KB" if tamanho_bytes < 1024*1024 else f"{tamanho_bytes / (1024*1024):.2f} MB"

    # 2. Conversão para Markdown
    ext = caminho_origem.suffix.lower()
    paginas_ocr = []
    total_paginas = 1

    motor_usado = "PyMuPDF"
    if ext == ".pdf":
        corpo_md, total_paginas, paginas_ocr, motor_usado = converter_pdf_para_md(
            caminho_origem,
            forcar_ocr=cfg["forcar_ocr"],
            nome_arquivo=nome_arquivo,
            modo_chave=modo_chave,
            t_inicio=t_inicio,
        )
    elif ext in {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}:
        corpo_md = converter_imagem_para_md(caminho_origem)
        paginas_ocr = [1]
        motor_usado = "Tesseract OCR (Imagem Direta)"
    else:
        print(f"  [ignorado] Formato '{ext}' não suportado.", file=sys.stderr)
        return

    # 3. Tratamento de Anonimização se requerido
    texto_chave = None
    if cfg["anonimizar"]:
        referencia = f"{data_hoje}_{caminho_origem.stem}"
        corpo_md, texto_chave = anonimizar_conteudo(corpo_md, referencia)

    # 4. Construção do Cabeçalho de Rastreabilidade
    info_ocr = (
        f"{len(paginas_ocr)} página(s) ({', '.join(map(str, paginas_ocr))})"
        if paginas_ocr
        else "Nenhuma (texto nativo integral)"
    )

    cabecalho_meta = f"""<!--
==============================================================================
ARQUIVO ORIGINAL  : {nome_arquivo}
DATA DA CONVERSÃO : {data_hoje} ({hora_agora})
MODALIDADE        : {cfg['descricao']}
MOTOR PROCESSADOR : {motor_usado}
TAMANHO ORIGINAL  : {tamanho_legivel} ({tamanho_bytes} bytes)
TOTAL DE PÁGINAS  : {total_paginas}
PÁGINAS COM OCR   : {info_ocr}
HASH SHA-256      : {hash_orig}
PASTA DE ENTRADA  : arquivos_de_entrada/{modo_chave}/
PASTA DE DESTINO  : arquivos_convertidos/{modo_chave}/{data_hoje}/
==============================================================================
-->

# {caminho_origem.stem}

> **Referência ao Documento Original:** `{nome_arquivo}`  
> **Data de Conversão:** {hora_agora}  
> **Modo Operacional:** {cfg['descricao']}  
> **Motor de Processamento:** {motor_usado}  
> **Volume de Páginas:** {total_paginas} página(s)  
> **Intervenção OCR:** {info_ocr}  
> **Assinatura SHA-256:** `{hash_orig}`  

---

"""

    conteudo_final_md = cabecalho_meta + corpo_md

    # 5. Salvamento dos Arquivos no Destino (com subpasta da data)
    nome_md = f"{caminho_origem.stem}.md"
    destino_md = obter_destino_unico(pasta_destino_dia, nome_md)
    destino_md.write_text(conteudo_final_md, encoding="utf-8")

    if texto_chave:
        # Nome espelhado (mesmo stem do .md, só com o prefixo da chave na
        # frente) — é o que permite ao modo "desanonimizacao" casar
        # automaticamente cada chave com o seu documento correspondente.
        destino_chave = obter_destino_unico(pasta_destino_dia, f"{PREFIXO_CHAVE}{nome_md}")
        destino_chave.write_text(texto_chave, encoding="utf-8")

    # 6. Transporte do arquivo original de entrada para a pasta do dia
    destino_arquivo_orig = obter_destino_unico(pasta_destino_dia, nome_arquivo)
    shutil.move(str(caminho_origem), str(destino_arquivo_orig))

    duracao_s = time.time() - t_inicio
    print(f"  ✔ Sucesso! ({duracao_s:.2f}s)")
    print(f"    - Motor utilizado: {motor_usado}")
    print(f"    - Arquivo original transportado para: {destino_arquivo_orig.relative_to(BASE_DIR)}")
    print(f"    - Markdown gerado com rastreabilidade: {destino_md.relative_to(BASE_DIR)}")

    # 7. Gravação de Log Diário em log/AAAA-MM-DD/
    registro_sucesso = f"""[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [SUCESSO] [MODO: {modo_chave.upper()}]
  Arquivo Original  : {nome_arquivo} ({tamanho_legivel})
  Hash SHA-256      : {hash_orig}
  Motor Utilizado   : {motor_usado}
  Total de Páginas  : {total_paginas} (Páginas OCR: {info_ocr})
  Arquivo Movido    : {destino_arquivo_orig.relative_to(BASE_DIR)}
  Markdown Gerado   : {destino_md.relative_to(BASE_DIR)}
  Tempo de Conversão: {duracao_s:.2f}s
------------------------------------------------------------------------------"""
    gravar_log(data_hoje, registro_sucesso)

    # 8. Atualiza estado para ocioso
    finalizar_progresso(nome_arquivo, total_paginas, duracao_s, motor_usado)


def eh_arquivo_chave(caminho: Path) -> bool:
    """Identifica se um .md em arquivos_de_entrada/desanonimizacao/ é uma chave (e não
    o documento anonimizado), pelo prefixo do nome ou, se o nome tiver sido
    alterado, pelo conteúdo do cabeçalho."""
    if caminho.name.lower().startswith(PREFIXO_CHAVE):
        return True
    try:
        inicio = caminho.read_text(encoding="utf-8", errors="ignore")[:200]
    except Exception:
        return False
    return "Chave de Desanonimização" in inicio


def _codigo_ref(nome: str) -> str | None:
    m = RE_REF_CODE.search(nome)
    return m.group(1).lower() if m else None


def carregar_mapa_chave(caminho_chave: Path) -> dict[str, str]:
    """Lê um arquivo de chave e devolve {rotulo: texto_original}, a partir
    das linhas 'rotulo → texto original' geradas por gerar_markdown_chave."""
    texto = caminho_chave.read_text(encoding="utf-8")
    return {m.group(1): m.group(2).strip() for m in RE_LINHA_CHAVE.finditer(texto)}


def desanonimizar_texto(texto: str, mapa: dict[str, str]) -> str:
    """Substitui cada rótulo '[rotulo]' pelo texto original correspondente."""
    for rotulo, original in mapa.items():
        texto = texto.replace(f"[{rotulo}]", original)
    return texto


def parear_chave_com_documentos(chave: Path, candidatos: list[Path]) -> list[Path]:
    """
    Descobre quais arquivos, dentre os candidatos anexados junto com a
    chave, pertencem a ela — permitindo que vários pares (documento +
    chave) sejam soltos juntos em arquivos_de_entrada/desanonimizacao/ sem se
    confundirem. Duas estratégias, na ordem:

      1) Nome espelhado: 'chave_de_desanonimizacao_<nome>.md' casa com o
         documento '<nome>.md' exatamente — é assim que o próprio
         auto_conversor.py nomeia a chave no modo "anonimizacao".
      2) Código de referência 'ref-XXXXXX' compartilhado no nome de ambos
         os arquivos — é assim que pdf_to_md_anonimizado.py nomeia os
         arquivos (deliberadamente sem o nome original do PDF).
    """
    if chave.name.lower().startswith(PREFIXO_CHAVE):
        nome_espelhado = chave.name[len(PREFIXO_CHAVE):]
        pareados = [d for d in candidatos if d.name == nome_espelhado]
        if pareados:
            return pareados

    codigo = _codigo_ref(chave.name)
    if codigo:
        return [d for d in candidatos if _codigo_ref(d.name) == codigo]

    return []


def processar_fila_desanonimizacao() -> int:
    """
    Varre arquivos_de_entrada/desanonimizacao/: para cada chave encontrada, localiza
    o(s) documento(s) anonimizado(s) correspondente(s) entre os arquivos
    anexados, gera o .md revertido (desanonimizado) e move os três
    arquivos (chave, documento original e o gerado) juntos para uma
    subpasta em arquivos_convertidos/desanonimizacao/AAAA-MM-DD/.
    """
    cfg = MODOS["desanonimizacao"]
    pasta_entrada = cfg["entrada"]
    pasta_saida_base = cfg["saida"]
    pasta_entrada.mkdir(parents=True, exist_ok=True)
    pasta_saida_base.mkdir(parents=True, exist_ok=True)

    candidatos = [
        p for p in pasta_entrada.iterdir()
        if p.is_file() and p.suffix.lower() == ".md" and not p.name.startswith(".") and arquivo_estavel(p)
    ]
    if not candidatos:
        return 0

    chaves = [p for p in candidatos if eh_arquivo_chave(p)]
    documentos_disponiveis = [p for p in candidatos if p not in chaves]

    data_hoje = datetime.now().strftime("%Y-%m-%d")
    processados = 0
    documentos_usados: set[Path] = set()

    for chave in chaves:
        pareados = [
            d for d in parear_chave_com_documentos(chave, documentos_disponiveis)
            if d not in documentos_usados
        ]

        if not pareados:
            print(f"  [aguardando] chave '{chave.name}': documento correspondente ainda não anexado.")
            continue

        mapa = carregar_mapa_chave(chave)
        if not mapa:
            print(f"  [aviso] chave '{chave.name}' não contém nenhum par rótulo→texto reconhecível.", file=sys.stderr)
            continue

        nome_pasta = pareados[0].stem
        pasta_grupo = obter_destino_unico(pasta_saida_base / data_hoje, nome_pasta)
        pasta_grupo.mkdir(parents=True, exist_ok=True)

        nomes_documentos = []
        for doc in pareados:
            texto_anonimizado = doc.read_text(encoding="utf-8")
            texto_revertido = desanonimizar_texto(texto_anonimizado, mapa)

            destino_gerado = obter_destino_unico(pasta_grupo, f"desanonimizado_{doc.name}")
            destino_gerado.write_text(texto_revertido, encoding="utf-8")

            destino_doc = obter_destino_unico(pasta_grupo, doc.name)
            shutil.move(str(doc), str(destino_doc))

            documentos_usados.add(doc)
            nomes_documentos.append(doc.name)
            processados += 1
            print(f"  ✔ Desanonimizado: '{doc.name}' -> {destino_gerado.relative_to(BASE_DIR)}")

        destino_chave = obter_destino_unico(pasta_grupo, chave.name)
        shutil.move(str(chave), str(destino_chave))

        registro_sucesso = f"""[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [SUCESSO] [MODO: DESANONIMIZACAO]
  Chave Utilizada   : {chave.name}
  Documento(s)      : {', '.join(nomes_documentos)}
  Pasta de Destino  : {pasta_grupo.relative_to(BASE_DIR)}
------------------------------------------------------------------------------"""
        gravar_log(data_hoje, registro_sucesso)

    for doc in documentos_disponiveis:
        if doc not in documentos_usados:
            print(f"  [aguardando] documento '{doc.name}': chave correspondente ainda não anexada.")

    return processados


def varrer_e_processar_filas() -> int:
    """Varre as pastas de entrada e processa todos os arquivos pendentes."""
    arquivos_processados = 0

    for modo_chave, cfg in MODOS.items():
        if modo_chave == "desanonimizacao":
            continue  # tratado à parte: pareamento de chave + documento, não conversão de PDF/imagem

        pasta_entrada = cfg["entrada"]
        if not pasta_entrada.exists():
            pasta_entrada.mkdir(parents=True, exist_ok=True)
            continue

        candidatos = [
            p for p in pasta_entrada.iterdir()
            if p.is_file() and p.suffix.lower() in EXTENSOES_SUPORTADAS and not p.name.startswith(".")
        ]

        for p in sorted(candidatos):
            if arquivo_estavel(p):
                try:
                    processar_arquivo(p, modo_chave)
                    arquivos_processados += 1
                except Exception as e:
                    print(f"  [erro fatal] Falha ao converter {p.name}: {e}", file=sys.stderr)
                    data_hoje = datetime.now().strftime("%Y-%m-%d")
                    registro_erro = f"""[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [ERRO] [MODO: {modo_chave.upper()}]
  Arquivo com Falha : {p.name}
  Pasta de Origem   : {p.relative_to(BASE_DIR)}
  Mensagem de Erro  : {str(e)}
------------------------------------------------------------------------------"""
                    gravar_log(data_hoje, registro_erro)

    arquivos_processados += processar_fila_desanonimizacao()

    return arquivos_processados


def exibir_status():
    """Exibe relatório das filas de conversão atuais e totais processados."""
    print("=" * 75)
    print(" STATUS DO SISTEMA DE CONVERSÃO LOCAL")
    print("=" * 75)
    for modo_chave, cfg in MODOS.items():
        entrada = cfg["entrada"]
        saida = cfg["saida"]
        extensoes_modo = {".md"} if modo_chave == "desanonimizacao" else EXTENSOES_SUPORTADAS
        qtd_pendentes = len([
            p for p in entrada.glob("*") if p.is_file() and p.suffix.lower() in extensoes_modo
        ]) if entrada.exists() else 0
        total_subpastas_data = len([p for p in saida.glob("*") if p.is_dir() and not p.name.startswith(".")]) if saida.exists() else 0

        print(f"Modo: {modo_chave.upper()} ({cfg['descricao']})")
        print(f"  Entrada : {entrada.relative_to(BASE_DIR)} -> {qtd_pendentes} arquivo(s) pendente(s)")
        print(f"  Saída   : {saida.relative_to(BASE_DIR)} -> {total_subpastas_data} lote(s) diário(s)")
        print("-" * 75)

    total_logs = len([p for p in LOG_DIR.glob("*") if p.is_dir() and not p.name.startswith(".")]) if LOG_DIR.exists() else 0
    print(f"Logs Diários: {LOG_DIR.relative_to(BASE_DIR)} -> {total_logs} subpasta(s) diária(s)")
    print("=" * 75)


def consultar_progresso():
    """Consulta o progresso em tempo real gravado no arquivo de estado."""
    prog_json = LOG_DIR / "progresso.json"
    if not prog_json.exists():
        print("Status: Ocioso (nenhuma conversão em andamento).")
        return

    try:
        dados = json.loads(prog_json.read_text(encoding="utf-8"))
        if dados.get("status") == "processando":
            print("=" * 75)
            print(" PROGRESSO DA CONVERSÃO EM TEMPO REAL")
            print("=" * 75)
            print(f"Arquivo     : {dados.get('arquivo')}")
            print(f"Modalidade  : {dados.get('modo', '').upper()}")
            if dados.get("fase"):
                print(f"Fase        : {dados.get('fase')}")
            print(f"Página      : {dados.get('pagina_atual')} de {dados.get('total_paginas')} ({dados.get('porcentagem')}%)")
            print(f"Páginas OCR : {dados.get('paginas_com_ocr')}")
            print(f"Decorrido   : {dados.get('tempo_decorrido')}")
            print(f"Restante est: ~{dados.get('tempo_restante_estimado')}")
            print(f"Atualizado  : {dados.get('atualizado_em')}")
            print("=" * 75)
        else:
            print("=" * 75)
            print(" STATUS DO CONVERSOR: OCIOSO")
            print("=" * 75)
            print(f"Último arquivo processado : {dados.get('ultimo_arquivo')}")
            if dados.get("motor_utilizado"):
                print(f"Motor utilizado           : {dados.get('motor_utilizado')}")
            print(f"Total de páginas          : {dados.get('total_paginas')}")
            print(f"Tempo total gasto         : {dados.get('duracao_total')}")
            print(f"Concluído em              : {dados.get('concluido_em')}")
            print("=" * 75)
    except Exception as e:
        print(f"Erro ao consultar progresso: {e}")


def modo_vigilancia(intervalo: int = 3):
    """Executa vigilância contínua das pastas."""
    print(f"=== Iniciando Vigilância Contínua (Intervalo: {intervalo}s) ===")
    print("Pastas monitoradas:")
    for m, c in MODOS.items():
        print(f"  [{m}] {c['entrada']}")
    print("Pressione Ctrl+C para encerrar.\n")

    try:
        while True:
            varrer_e_processar_filas()
            time.sleep(intervalo)
    except KeyboardInterrupt:
        print("\n[Vigilância encerrada pelo usuário]")


def main():
    parser = argparse.ArgumentParser(description="Conversor Automático de Documentos para Markdown.")
    parser.add_argument("--watch", "--vigiar", action="store_true", help="Monitora as pastas continuamente")
    parser.add_argument("--intervalo", type=int, default=3, help="Intervalo de checagem do modo contínuo em segundos (padrão: 3)")
    parser.add_argument("--status", action="store_true", help="Exibe relatório das pastas e filas")
    parser.add_argument("--progresso", action="store_true", help="Exibe o progresso em tempo real da conversão ativa")
    args = parser.parse_args()

    # Garante estrutura base
    for cfg in MODOS.values():
        cfg["entrada"].mkdir(parents=True, exist_ok=True)
        cfg["saida"].mkdir(parents=True, exist_ok=True)

    if args.progresso:
        consultar_progresso()
        return

    if args.status:
        exibir_status()
        return

    if args.watch:
        modo_vigilancia(args.intervalo)
    else:
        processados = varrer_e_processar_filas()
        if processados == 0:
            print("Nenhum arquivo pendente nas pastas de entrada (arquivos_de_entrada/padrao, arquivos_de_entrada/ocr, arquivos_de_entrada/anonimizacao).")
        else:
            print(f"\nProcessamento concluído: {processados} arquivo(s) convertido(s) e transportado(s).")


if __name__ == "__main__":
    main()
