#!/usr/bin/env python3
"""
pdf_to_md_anonimizado.py — Converte um PDF em Markdown (com marcação de
página) E ANONIMIZA o conteúdo, em linha com o espírito da Resolução CNJ
nº 615/2025 (art. 7º, §2º; art. 19, §3º, IV; art. 30 e §1º), que exige
anonimização/pseudonimização "na origem" de dados pessoais e sigilosos
antes de submetê-los a ferramentas de inteligência artificial externas.

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
    python3 pdf_to_md_anonimizado.py arquivo.pdf
    python3 pdf_to_md_anonimizado.py arquivo.pdf --pasta-saida ./saida
    python3 pdf_to_md_anonimizado.py *.pdf
    python3 pdf_to_md_anonimizado.py arquivo.pdf --forcar-ocr
    python3 pdf_to_md_anonimizado.py arquivo.pdf --idioma eng

Saída — o nome do PDF de origem NÃO é usado no nome dos arquivos gerados
(ele próprio pode identificar o processo/as partes). Em vez disso, cada
conversão recebe uma referência anônima com data e um código curto, por
exemplo, para um PDF convertido em 07/09/2026:

    projeto_2026-09-07_ref-a1b2c3.md                    -> texto anonimizado,
                                                            com marcação de
                                                            página
    chave_de_desanonimizacao_2026-09-07_ref-a1b2c3.md   -> tabela de
                                                            correspondência:
                                                            cada rótulo, o
                                                            texto original
                                                            substituído e as
                                                            páginas em que
                                                            ocorreu

O código (ex.: "a1b2c3") é derivado do conteúdo do PDF, não do nome do
arquivo nem de nenhum dado pessoal — dois PDFs diferentes praticamente
nunca geram o mesmo código, mas o mesmo PDF processado de novo gera
sempre o mesmo código (útil para saber se já foi convertido antes, e é
também o que permite ao `auto_conversor.py` casar automaticamente um
documento anonimizado com a sua chave em `arquivos_de_entrada/desanonimizacao/`).

IMPORTANTE — LEIA COM ATENÇÃO:
    A detecção de dados a anonimizar é feita por padrões (regex) e por
    heurística de nomes próprios, TOTALMENTE AUTOMÁTICA, sem qualquer
    lista prévia fornecida pelo usuário. Isso é conveniente, mas tem
    limites técnicos reais:

    - CPF, CNPJ, número de processo (padrão CNJ), telefone, e-mail, CEP
      e RG são detectados com alta confiabilidade, pois seguem formatos
      bem definidos.
    - NOMES DE PESSOAS (partes, testemunhas, juiz, promotor, defensores,
      delegados, advogados, servidores) são detectados por heurística
      (sequências de palavras capitalizadas, títulos como "Dr.", "Sr.",
      "MM. Juiz(a)", etc.). Isso PODE falhar: tanto deixando de detectar
      um nome fora do padrão esperado, quanto anonimizando por engano
      algo que não é um nome (falso positivo).
    - Por padrão, TODO nome de pessoa detectado vira "nome_1", "nome_2"
      etc., em ordem de primeira aparição no documento — sem tentar
      identificar o papel processual (réu, vítima, advogado...), pois
      essa classificação exigiria contexto que nem sempre é confiável
      automaticamente.

    Por isso, SEMPRE revise o arquivo "chave_de_desanonimizacao_*.md"
    gerado antes de considerar o "projeto_*.md" seguro para uso externo,
    especialmente em processos sob segredo de justiça. Este script é uma
    ferramenta de apoio, não um substituto do julgamento humano sobre o
    que é sigiloso.
"""

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from collections import OrderedDict
from datetime import datetime
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


# ---------------------------------------------------------------------------
# Extração de texto (idêntico ao pdf_to_md.py)
# ---------------------------------------------------------------------------

def extrair_texto_nativo(pagina):
    try:
        texto = pagina.extract_text() or ""
    except Exception:
        texto = ""
    return texto.strip()


def ocr_pagina(caminho_pdf, numero_pagina, idioma):
    """Renderiza uma única página do PDF como imagem e roda OCR com máscara de borda e remoção de réguas."""
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
    texto incompleto/corrompido em páginas escaneadas tortas, rotacionadas
    ou ruidosas — a causa raiz tanto de páginas "em branco"/com erro quanto
    de dados pessoais (ex.: nome de mãe/pai no campo "Filiação") não
    detectados pela anonimização, já que o motor de anonimização não
    consegue mascarar o que o OCR nunca extraiu corretamente.

    forcar_ocr=False usa --skip-text (modo híbrido: preserva o texto
    nativo já bom das páginas digitais e só aplica deskew/limpeza + OCR
    nas páginas sem texto) — é o modo usado normalmente por este script.
    forcar_ocr=True usa --force-ocr (reprocessa todas as páginas via OCR).
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


def extrair_paginas(caminho_pdf: Path, forcar_ocr: bool, idioma: str, verbose=True):
    """Retorna lista de (numero_pagina, texto) e lista de páginas que usaram OCR.

    Tenta primeiro o pré-processamento com OCRmyPDF (deskew/rotação/limpeza
    — ver _pre_processar_com_ocrmypdf); só cai no OCR página a página via
    Tesseract cru (sem pré-processamento) se o OCRmyPDF não estiver
    disponível ou falhar.
    """
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

    tmp_dir = Path(tempfile.mkdtemp(prefix="pdf_to_md_anon_ocrmypdf_"))
    pdf_temp = tmp_dir / f"processado_{int(time.time() * 1000)}.pdf"
    sucesso_ocrmypdf = False

    try:
        sucesso_ocrmypdf = _pre_processar_com_ocrmypdf(caminho_pdf, pdf_temp, idioma, forcar_ocr, verbose=verbose)
        if sucesso_ocrmypdf:
            leitor = PdfReader(str(pdf_temp))
            total_paginas = len(leitor.pages)

        paginas = []
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
                texto = ""

            paginas.append((i, texto))

            if verbose:
                marca = "OCR" if usado_ocr else "texto nativo"
                print(f"  página {i}/{total_paginas} ({marca}) — {len(texto)} caracteres")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return paginas, paginas_com_ocr, total_paginas


# ---------------------------------------------------------------------------
# Motor de anonimização
# ---------------------------------------------------------------------------

# Palavras funcionais/jurídicas comuns que começam com maiúscula e que NÃO
# devem, sozinhas, disparar a heurística de "nome próprio" quando aparecem
# em sequência (evita falsos positivos como "Ministério Público",
# "Código de Processo Penal", "Poder Judiciário").
STOPWORDS_MAIUSCULAS = {
    "MINISTERIO", "MINISTÉRIO", "PUBLICO", "PÚBLICO", "PODER", "JUDICIARIO",
    "JUDICIÁRIO", "CODIGO", "CÓDIGO", "PROCESSO", "PROCESSUAL", "PENAL",
    "CIVIL", "CONSTITUICAO", "CONSTITUIÇÃO", "FEDERAL", "ESTADO", "ESTADUAL",
    "UNIAO", "UNIÃO", "REPUBLICA", "REPÚBLICA", "BRASIL", "BRASILEIRA",
    "SECRETARIA", "SECAO", "SEÇÃO", "VARA", "COMARCA", "FORUM", "FÓRUM",
    "TRIBUNAL", "SUPERIOR", "JUSTICA", "JUSTIÇA", "DIREITO", "LEI",
    "DECRETO", "SUMULA", "SÚMULA", "ARTIGO", "PARAGRAFO", "PARÁGRAFO",
    "INCISO", "CAPITULO", "CAPÍTULO", "TITULO", "TÍTULO", "LIVRO", "SECRETARIA",
    "AUTOS", "PROCEDIMENTO", "ACAO", "AÇÃO", "RECURSO", "APELACAO", "APELAÇÃO",
    "SENTENCA", "SENTENÇA", "DECISAO", "DECISÃO", "DESPACHO", "ACORDAO",
    "ACÓRDÃO", "CERTIDAO", "CERTIDÃO", "MANDADO", "OFICIO", "OFÍCIO",
    "ANEXO", "REGISTRO", "CARTORIO", "CARTÓRIO", "DELEGACIA", "DISTRITO",
    "BAIRRO", "CENTRO", "RUA", "AVENIDA", "MUNICIPIO", "MUNICÍPIO",
    "COMARCA", "REGIAO", "REGIÃO", "SEGREDO", "MERITISSIMO", "MERITÍSSIMO",
    "MM", "TESTEMUNHA", "REU", "RÉU", "VITIMA", "VÍTIMA", "AUTOR", "AUTORA",
    "DENUNCIADO", "DENUNCIADA", "ACUSADO", "ACUSADA", "APENADO", "APENADA",
    "IMPETRANTE", "IMPETRADO", "EXEQUENTE", "EXECUTADO", "REQUERENTE",
    "REQUERIDO", "REQUERIDA", "APELANTE", "APELADO", "RECORRENTE", "RECORRIDO",
    "GOVERNO", "UNIDADE", "HOMICIDIOS", "HOMICÍDIOS", "SEGUIMENTO",
    "SEGMENTO", "POLICIA", "POLÍCIA", "CIVIL", "MILITAR", "BOLETIM",
    "OCORRENCIA", "OCORRÊNCIA", "RELATO", "HISTORICO", "HISTÓRICO",
    "ASSINATURAS", "ASSINATURA", "MATRICULA", "MATRÍCULA", "RESPONSAVEL",
    "RESPONSÁVEL", "CONTRAVENCAO", "CONTRAVENÇÃO", "BRASILEIRO",
    "BRASILEIRA", "GRUPO", "SUBGRUPO", "CELULARES", "COR", "PRETA",
    "BRANCA", "MARCA", "MODELO", "DELEGACIA", "PLANTAO", "PLANTÃO",
    "COORDENACAO", "COORDENAÇÃO", "EQUIPE", "ANEXO", "FOTOGRAFICO",
    "FOTOGRÁFICO", "DILIGENCIAS", "DILIGÊNCIAS", "LEVANTAMENTOS",
    "CORRIGIR", "ALTERAR", "EXCLUIR", "VISUALIZAR", "IMPRIMIR", "ASSINAR",
    "PENDENTE", "CONCLUIDO", "CONCLUÍDO", "DEFERIDO", "INDEFERIDO",
    "PUBLICADO", "DISTRIBUIDO", "DISTRIBUÍDO", "AUTUADO", "PROTOCOLADO",
    # Rótulos e cabeçalhos de campo comuns em formulários, boletins de
    # ocorrência e autos policiais/periciais — sem isso, frases como
    # "Data de Nascimento", "Local do Fato" e "Tipo do Local" são
    # confundidas com nome de pessoa pela heurística de maiúsculas.
    "DATA", "HORA", "LOCAL", "TIPO", "DESCRICAO", "DESCRIÇÃO", "SITUACAO",
    "SITUAÇÃO", "DOCUMENTO", "DOCUMENTOS", "NASCIMENTO", "IDADE", "SEXO",
    "COR", "RACA", "RAÇA", "ESTADO CIVIL", "ESCOLARIDADE", "PROFISSAO",
    "PROFISSÃO", "NATURALIDADE", "NACIONALIDADE", "FILIACAO", "FILIAÇÃO",
    "ENDERECO", "ENDEREÇO", "COMPLEMENTO", "TELEFONE", "CELULAR", "EMAIL",
    "E-MAIL", "NOME", "APELIDO", "VULGO", "ALCUNHA", "QUALIFICACAO",
    "QUALIFICAÇÃO", "ENVOLVIDO", "ENVOLVIMENTO", "ENVOLVIMENTOS",
    "IDENTIFICADOR", "UNICO", "ÚNICO", "POSSUIDOR", "PROPRIETARIO",
    "PROPRIETÁRIO", "EXIBIDOR", "ATENDENTE", "SOLICITANTE", "OPERADOR",
    "APROXIMADA", "APROXIMADO", "INICIO", "INÍCIO", "FIM", "FATO", "FATOS",
    "NATUREZA", "MEIO", "EMPREGADO", "ARMA", "FOGO", "VESTUARIO",
    "VESTUÁRIO", "OBSERVACAO", "OBSERVAÇÃO", "OBSERVACOES", "OBSERVAÇÕES",
    "CONFERENCIA", "CONFERÊNCIA", "IMPRESSO", "IMPRESSAO", "IMPRESSÃO",
    "PAGINA", "PÁGINA", "FLS", "FLS.", "ATENDIMENTO", "ATENDIMENTOS",
    "SOCIAL", "REDES", "LOTE", "QUADRA", "LOGRADOURO", "REFERENCIA",
    "REFERÊNCIA", "PONTO", "URBANA", "RURAL", "ZONA", "CASADO", "SOLTEIRO",
    "DIVORCIADO", "VIUVO", "VIÚVO", "MASCULINO", "FEMININO", "COMPLETO",
    "INCOMPLETO", "ENSINO", "MEDIO", "MÉDIO", "FUNDAMENTAL", "SUPERIOR",
    "ANALISE", "ANÁLISE", "ENVIO", "RECEBEU", "ORGAO", "ÓRGÃO", "CUSTODIA",
    "CUSTÓDIA", "CENTRAL", "LACRE", "PROTOCOLO", "COLETA", "ENTREGA",
    "VESTIGIO", "VESTÍGIO", "FORMULARIO", "FORMULÁRIO", "GERAIS", "DADOS",
    "TRANSCRICAO", "TRANSCRIÇÃO", "SINTESE", "SÍNTESE", "AUDIOVISUAL",
    "REALIZADA", "AUTORIZA", "EXPRESSAMENTE", "TERMO", "DEPOIMENTO",
    "AUTORIDADE", "TEMPO", "SOLICITACAO", "SOLICITAÇÃO", "APOIO", "MESA",
    "DESPACHANTE", "ANALISE DO TEMPO", "IMPRESSAO DIGITAL", "POLEGAR",
    "INDICADOR", "MEDIO", "ANELAR", "MINIMO", "MÍNIMO", "ESQUERDA",
    "DIREITA", "CABELOS", "OBSERVACAO CONFERENCIA", "EMISSAO", "EMISSÃO",
    "CATEGORIA", "CLASSIFICACAO", "CLASSIFICAÇÃO", "NUMERO", "NÚMERO",
    "QUANTIDADE", "VALOR", "MODELO", "COMPLEMENTO OBSERVACOES",
    # Termos jurídicos/institucionais genéricos e de trâmite processual —
    # aparecem sozinhos como título/seção com frequência, mas não
    # identificam ninguém.
    "INQUERITO", "INQUÉRITO", "POLICIAL", "EXCELENCIA", "EXCELÊNCIA",
    "VOSSA", "RECOGNICAO", "RECOGNIÇÃO", "VISUOGRAFICA", "VISUOGRÁFICA",
    "INSTITUTO", "MEDICO", "MÉDICO", "LEGAL", "CRIMINALISTICA",
    "CRIMINALÍSTICA", "IDENTIFICACAO", "IDENTIFICAÇÃO", "RELATORIO",
    "RELATÓRIO", "INVESTIGACAO", "INVESTIGAÇÃO", "PRELIMINAR",
    "QUALIFICADO", "QUALIFICADA", "TRAICAO", "TRAIÇÃO", "DISSIMULACAO",
    "DISSIMULAÇÃO", "OFENDIDO", "OFENDIDA", "DEFESA", "TESTEMUNHAS",
    "DECLARACOES", "DECLARAÇÕES", "PRESTADAS", "PELA", "AUTORIA",
    "DESCONHECIDA", "DESCONHECIDO", "CENA", "CRIME", "DINAMICA",
    "DINÂMICA", "POSSIVEL", "POSSÍVEL", "MOTIVACAO", "MOTIVAÇÃO",
    "PERTENCES", "ENCONTRADOS", "CAMERAS", "CÂMERAS", "SEGURANCA",
    "SEGURANÇA", "PUBLICA", "PÚBLICA", "NACIONAL", "FUNDO", "SEGURANCA PUBLICA",
    "INFORMACOES", "INFORMAÇÕES", "PRESTADAS PELA", "CAPITAL", "PESSOA",
    "IDENTIFICADO", "TIPIFICACAO", "TIPIFICAÇÃO", "ACIONAMENTO",
    "HORARIO", "HORÁRIO", "INSTITUICOES", "INSTITUIÇÕES", "PRESENTES",
    "PROFISSAO", "ANTECEDENTES", "CRIMINAIS", "VICIOS", "VÍCIOS",
    "LUGARES", "FREQUENTAR", "SUCINTA", "ULTIMAS", "ÚLTIMAS", "VINTE",
    "QUATRO", "MORTE", "RECENTE", "PRESUMIDA", "DECUBITO", "DECÚBITO",
    "VENTRAL", "LATERAL", "DORSAL", "PERFURO", "CONTUNDENTE", "PROJETEIS",
    "PROJÉTEIS", "CARTUCHOS", "IDENTIFICADO INTERNO", "EXTERNO", "TIPO DE",
    "OBSERVACOES", "VITIMAS", "VÍTIMAS", "SOBREVIVENTES", "INFORMANTE",
    "SUBTRACAO", "SUBTRAÇÃO", "OUTROS", "BENS", "VESTIGIOS", "AUTORES",
    "ROUBAS", "CAMUFLADAS", "GEOLOCALIZACAO", "GEOLOCALIZAÇÃO",
    "PANORAMICA", "PANORÂMICA", "FOTO", "ACESSO", "PORTA", "TERREO",
    "TÉRREO", "EDIFICIO", "EDIFÍCIO", "APARTAMENTO", "POSICAO", "POSIÇÃO",
    "ENCONTRADA", "FACIAL", "APRESENTA", "LESOES", "LESÕES", "PROJETIL",
    "PROJÉTIL", "CERVICAL", "LOCALIZADO", "PROXIMO", "PRÓXIMO", "CORPO",
    "PERNAS", "SIGLA", "PIXADA", "PAREDE", "DEFLAGRADOS", "ESTOJO",
    "FOTOS", "PESSOAIS", "MODALIDADE", "POLICIAMENTO", "SOLDADO",
    "SARGENTO", "TENTATIVA", "HOMICIDIO", "HOMICÍDIO", "RELATA", "OUVIU",
    "VARIOS", "VÁRIOS", "DISPAROS", "JOVEM", "CHAMADO", "VEIO", "OBITO",
    "ÓBITO", "ABERTAS", "PORTAS", "AUTORES DOS", "SABE", "INFORMAR",
    "QUANTOS", "FORAM", "CONJUNTO", "SEXO", "MASCULINO", "FEMININO",
    "OCORREU", "RESIDENCIAL", "PRESENCA", "PRESENÇA", "FORENSIS", "GUIA",
    "VIA", "APOIO", "ATENDENTE", "PARA", "TRANSCRICAO", "TRANSCRIÇÃO",
    "DEPOIMENTO", "MEIO", "AUDIOVISUAL", "SINTESE", "SÍNTESE",
    "ARQUIVOS", "PETICIONADOS", "PETICIONAMENTO", "INICIAL", "GRAU",
    "REMESSA", "CITACAO", "CITAÇÃO", "INTIMACAO", "INTIMAÇÃO",
    "DESTINATARIO", "DESTINATÁRIO", "ATO", "TEOR", "PORTAL", "ELETRONICO",
    "ELETRÔNICO", "CIENCIA", "CIÊNCIA", "PROCURADORIA", "GERAL",
    "REPRESENTACAO", "REPRESENTAÇÃO", "QUEBRA", "SIGILOS", "TELEMATICOS",
    "TELEMÁTICOS", "BANCARIOS", "BANCÁRIOS", "SIGILO", "TELEMATICO",
    "TELEMÁTICO", "BANCARIO", "BANCÁRIO", "DENUNCIACAO", "DENUNCIAÇÃO",
    "CALUNIOSA", "COMUNICACAO", "COMUNICAÇÃO", "FALSA", "EXIBICAO",
    "EXIBIÇÃO", "APREENSAO", "APREENSÃO", "INTELIGENCIA", "INTELIGÊNCIA",
    "AFASTAMENTO", "EXTRACAO", "EXTRAÇÃO", "DISPOSITIVOS", "MOVEIS",
    "MÓVEIS", "MARCO", "REGULATORIO", "REGULATÓRIO", "INTERNET",
    # Palavras gramaticais curtas que só aparecem capitalizadas por sorte
    # de posição na frase (nunca fazem parte de um nome de pessoa).
    "EM", "UM", "UMA", "NO", "NA", "NOS", "NAS", "AO", "AOS", "PELO",
    "PELA", "PELOS", "PELAS", "COM", "SEM", "SOB", "SOBRE", "ATE", "ATÉ",
    "QUE", "QUAL", "QUAIS", "COMO", "QUANDO", "ONDE", "SE", "OU", "MAS",
    "POR", "SEU", "SUA", "SEUS", "SUAS",
}

# Títulos/pronomes de tratamento que, quando líderam um bloco capturado,
# devem ser descartados do NÚCLEO do nome (o rótulo cobre só a pessoa,
# não o cargo/título dela).
TITULOS_A_DESCARTAR = {
    "DR", "DRA", "SR", "SRA", "SRTA", "MM", "EXMO", "EXMA",
    "EXCELENTISSIMO", "EXCELENTÍSSIMO", "EXCELENTISSIMA", "EXCELENTÍSSIMA",
    "DOUTOR", "DOUTORA", "JUIZ", "JUÍZA", "JUIZA", "DESEMBARGADOR",
    "DESEMBARGADORA", "PROMOTOR", "PROMOTORA", "DEFENSOR", "DEFENSORA",
    "DELEGADO", "DELEGADA", "ADVOGADO", "ADVOGADA", "PERITO", "PERITA",
    "ESCRIVAO", "ESCRIVÃO", "ESCRIVA", "ESCRIVÃ", "OFICIAL", "PUBLICO",
    "PÚBLICO",
}

PARTICULAS_NOME = {"de", "da", "do", "das", "dos", "e"}

TITULOS_PESSOA = (
    r"(?:Dr\.?|Dra\.?|Sr\.?|Sra\.?|Srta\.?|MM\.?|Exmo\.?|Exma\.?|"
    r"Excelent[ií]ssimo|Excelent[ií]ssima|Doutor|Doutora|"
    r"Juiz|Ju[íi]za|Desembargador|Desembargadora|Promotor|Promotora|"
    r"Defensor|Defensora|Delegado|Delegada|Advogado|Advogada|Perito|Perita|"
    r"Escriv[ãa]o|Escriv[ãa]|Oficial)"
)

# Observação: este padrão cobre apenas o TIPO/NOME INSTITUCIONAL do
# tribunal/vara/comarca (ex.: "Tribunal de Justiça", "Vara Criminal",
# "Comarca"), SEM tentar capturar o nome do estado/cidade embutido nele —
# isso já foi resolvido antes, pela categoria "estado"/"municipio" (ver
# RE_ESTADO/RE_MUNICIPIO), que roda primeiro. Assim, "Tribunal de Justiça
# do Estado de Alagoas" chega aqui já como "Tribunal de Justiça do Estado
# [estado_1]", e este padrão não precisa (nem deve) capturar mais nada —
# o órgão continua identificável (útil p/ pesquisa jurídica: TJ x STJ x
# TRF importa), só o nome geográfico fica oculto.
# A comparação é feita sobre uma versão do texto sem acento (comum em OCR
# e digitação informal, ex.: "JUSTICA" por "Justiça") — ver uso em
# processar_pagina — mas a substituição preserva o texto ORIGINAL.
TRIBUNAL_PADRAO = re.compile(
    r"\b(?:"
    r"Tribunal de Justica|"
    r"Tribunal Regional Federal|"
    r"Tribunal Regional do Trabalho|"
    r"Tribunal Regional Eleitoral|"
    r"Superior Tribunal de Justica|"
    r"Supremo Tribunal Federal|"
    r"Superior Tribunal Militar|"
    r"TJ[A-Z]{2}|TRF\d|TRT\d{0,2}|TRE[A-Z]{2}|STJ|STF|STM|"
    r"Vara (?:Criminal|Civel|de Familia|do Trabalho|Federal)\b|"
    r"Comarca\b|"
    r"Forum\b"
    r")",
    re.IGNORECASE,
)

def _remover_acentos(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


# Estados e capitais brasileiros. Usados para anonimizar APENAS o nome do
# estado/município — mesmo dentro do nome de um órgão/instituição (ex.:
# "Governo do Estado de Alagoas" -> "Governo do Estado [estado_1]",
# "Polícia Civil do Estado de Alagoas" -> "Polícia Civil do Estado
# [estado_1]") — preservando o restante do nome da instituição, que por
# si só não identifica o processo.
ESTADOS_BRASIL = [
    "Acre", "Alagoas", "Amapá", "Amazonas", "Bahia", "Ceará",
    "Distrito Federal", "Espírito Santo", "Goiás", "Maranhão",
    "Mato Grosso do Sul", "Mato Grosso", "Minas Gerais", "Pará", "Paraíba",
    "Paraná", "Pernambuco", "Piauí", "Rio de Janeiro",
    "Rio Grande do Norte", "Rio Grande do Sul", "Rondônia", "Roraima",
    "Santa Catarina", "São Paulo", "Sergipe", "Tocantins",
]

CAPITAIS_BRASIL = [
    "Rio Branco", "Maceió", "Macapá", "Manaus", "Salvador", "Fortaleza",
    "Brasília", "Vitória", "Goiânia", "São Luís", "Campo Grande", "Cuiabá",
    "Belo Horizonte", "Belém", "João Pessoa", "Curitiba", "Recife",
    "Teresina", "Natal", "Porto Alegre", "Porto Velho", "Boa Vista",
    "Florianópolis", "São Paulo", "Aracaju", "Palmas",
]


def _construir_padrao_lista(nomes):
    """
    Constrói um regex que casa qualquer item da lista, tolerante a
    acentuação (compara contra texto sem acento — ver uso em
    processar_pagina), do mais longo para o mais curto (evita que
    "Mato Grosso" capture parcialmente "Mato Grosso do Sul").

    DELIBERADAMENTE SEM re.IGNORECASE: só reconhece a forma Capitalizada
    normal (ex.: "Alagoas") ou TODA EM CAIXA ALTA (ex.: "ALAGOAS") — nunca
    a palavra solta em minúsculas. Isso evita que uma preposição comum
    colida com um nome de estado quando o acento é removido (ex.: a
    preposição "para" e o estado "Pará" ficam idênticos sem acento; exigir
    maiúscula inicial resolve isso sem excluir "PARÁ" em textos que citam
    o estado todo em caixa alta).
    """
    nomes_sem_acento = sorted({_remover_acentos(n) for n in nomes}, key=len, reverse=True)
    variantes = set()
    for n in nomes_sem_acento:
        variantes.add(n)          # "Mato Grosso" / "Alagoas"
        variantes.add(n.upper())  # "MATO GROSSO" / "ALAGOAS"
    variantes_ordenadas = sorted(variantes, key=len, reverse=True)
    alternativas = "|".join(re.escape(v) for v in variantes_ordenadas)
    return re.compile(r"\b(?:" + alternativas + r")\b")


RE_ESTADO = _construir_padrao_lista(ESTADOS_BRASIL)
RE_MUNICIPIO = _construir_padrao_lista(CAPITAIS_BRASIL)

# "Pará" (estado) colide com "para" (preposição comum), inclusive quando
# capitalizada por estar no início de uma frase (ex.: "Para conferir o
# original..."). Por isso essa ocorrência específica só é anonimizada
# quando há um gatilho de contexto claramente geográfico IMEDIATAMENTE
# adjacente (poucas palavras antes ou depois, não em qualquer lugar de
# uma janela ampla — senão um "Estado" de uma frase anterior não
# relacionada pode disparar o gatilho por engano).
_GATILHO_ANTES_PARA = re.compile(
    r"(?:Estado|Municipio|Município|Comarca|Cidade)\s+d?[eo]?s?\s*$",
    re.IGNORECASE,
)
_GATILHO_DEPOIS_PARA = re.compile(
    r"^\s*[,\-/]?\s*(?:PA\b|,|\.)",
)


def _tem_contexto_geografico(texto_sem_acento: str, inicio: int, fim: int, janela: int = 18) -> bool:
    trecho_antes = texto_sem_acento[max(0, inicio - janela):inicio]
    trecho_depois = texto_sem_acento[fim:fim + 4]
    return bool(
        _GATILHO_ANTES_PARA.search(trecho_antes)
        or _GATILHO_DEPOIS_PARA.match(trecho_depois)
    )

RE_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
RE_CNPJ = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
RE_PROCESSO_CNJ = re.compile(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b")
RE_CEP = re.compile(r"\b\d{5}-\d{3}\b")
RE_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
RE_TELEFONE = re.compile(
    r"(?<!\d)(?:\+?55\s?)?(?:\(?\d{2}\)?[\s.-]?)?(?:9\s?)?\d{4}[\s.-]?\d{4}(?!\d)"
)
RE_RG = re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}-?[\dXx]\b")

RE_ENDERECO = re.compile(
    r"\b(?:Rua|Av\.|Avenida|Alameda|Travessa|Rodovia|Praça|Estrada|Quadra|"
    r"Lote|Bloco)\s+[A-ZÀ-Úa-zà-ú0-9º°,\.\s]{3,60}?,?\s*n?[ºo°]?\s*\d{1,6}\b",
    re.IGNORECASE,
)

# Bloco bruto: uma ou mais palavras capitalizadas (ex.: "João da Silva"),
# permitindo partículas minúsculas (de/da/do/das/dos/e) somente quando
# IMEDIATAMENTE seguidas de outra palavra capitalizada. Este padrão é
# deliberadamente permissivo — a filtragem fina (remover títulos/
# stopwords, exigir 2+ palavras reais de 2+ letras) acontece depois, em
# _extrair_nucleo_nome, preservando os índices exatos de início/fim
# dentro do texto original para uma substituição precisa.
RE_BLOCO_MAIUSCULO = re.compile(
    r"\b[A-ZÀ-Ú][a-zà-ÿ'\-]+(?:\s+(?:(?:" + "|".join(PARTICULAS_NOME) +
    r")\s+)?[A-ZÀ-Ú][a-zà-ÿ'\-]+)*\b"
)

# Mesma ideia, mas para nomes escritos INTEIRAMENTE EM CAIXA ALTA — comum
# em boletins de ocorrência, autos policiais e blocos de assinatura
# digital (ex.: "DANILO TUZINO DE REZENDE", "IGOR NATAN CAVALCANTE DA
# SILVA GOMES"). Cada palavra precisa ter 2+ letras para não confundir
# iniciais soltas, numeração de artigo de lei (ex.: "339-A") ou siglas de
# 1 letra com nome de pessoa.
RE_BLOCO_CAIXA_ALTA = re.compile(
    r"\b[A-ZÀ-Ú]{2,}(?:\s+(?:(?:" + "|".join(p.upper() for p in PARTICULAS_NOME) +
    r")\s+)?[A-ZÀ-Ú]{2,})+\b"
)

RE_TITULO_NOME = re.compile(TITULOS_PESSOA + r"\.?\s+" + RE_BLOCO_MAIUSCULO.pattern)

# Rótulos de campos de formulário/BO/processo que, por definição, só podem
# conter nome de pessoa como valor. Diferente da heurística genérica acima
# (que exige 2+ palavras capitalizadas para evitar falso positivo), aqui o
# próprio rótulo já garante que o valor é um nome — então é seguro mascarar
# mesmo um fragmento de 1 palavra, o que é essencial quando o OCR degrada o
# texto (ruído, foto torta, baixa resolução) e só sobra um pedaço legível do
# nome. Esta é a correção direta para o caso relatado de nome de pai/mãe
# vazando na anonimização: o campo "Filiação" era detectado, mas o nome
# depois dele só era mascarado se batesse no padrão genérico de 2+ palavras
# "limpas" — um nome truncado ou com caractere trocado pelo OCR (ex.:
# "M4RIA", ou apenas "SILVA" sobrando de um nome maior) passava direto.
RE_CAMPO_PESSOAL = re.compile(
    r"\b(Filia[çc][ãa]o|Nome\s+d[ao]\s+M[ãa]e|Nome\s+d[oa]\s+Pai|"
    r"Genitor(?:a)?|Nome\s+d[ao]\s+Genitor(?:a)?|Nome\s+d[ao]\s+Declarante|"
    r"Nome\s+d[ao]\s+Testemunha|Nome\s+d[ao]\s+V[íi]tima|Nome\s+d[ao]\s+Autor(?:a)?|"
    r"Nome\s+d[ao]\s+Ofendid[ao]|Nome\s+Completo|Nome\s+Social)"
    r"(\s*[:\-]\s*)([^\n]{1,140})",
    re.IGNORECASE,
)

# Valores que, mesmo aparecendo como conteúdo de um campo pessoal, NÃO são
# nome de ninguém e não devem virar um rótulo "nome_N" (isso poluiria a
# chave de desanonimização com entradas falsas e sem utilidade).
PLACEHOLDERS_NEGATIVOS = {
    "NAO INFORMADO", "NAO INFORMADA", "IGNORADO", "IGNORADA", "NAO CONSTA",
    "N/A", "NA", "NI", "N/I", "SEM INFORMACAO", "NAO DECLARADO",
    "NAO DECLARADA", "PREJUDICADO", "PREJUDICADA", "DESCONHECIDO",
    "DESCONHECIDA", "FALECIDO", "FALECIDA", "NAO SABE",
    "NAO SOUBE INFORMAR", "EM BRANCO", "NAO SE APLICA", "AUSENTE",
}

# Separa dois nomes dentro do mesmo campo (comum em "Filiação: Mãe e Pai"),
# preservando o separador original na saída (vírgula, barra ou "e"/"E").
RE_SEPARADOR_NOME_CAMPO = re.compile(r"(,|;|/|\bE\b)", re.IGNORECASE)


def _normalizar(palavra: str) -> str:
    return _remover_acentos(palavra).upper().strip(".,;:")


def _e_stopword_juridica(palavra: str) -> bool:
    return _normalizar(palavra) in STOPWORDS_MAIUSCULAS


def _e_titulo(palavra: str) -> bool:
    return _normalizar(palavra) in TITULOS_A_DESCARTAR


def _extrair_nucleo_nome(bloco: str, min_palavras: int = 2):
    """
    Recebe um bloco bruto (ex.: "MM Juiz Carlos Eduardo Ramos" ou
    "Defensor Público Marcos Vinicius Oliveira") e devolve (inicio, fim,
    nucleo) delimitando, dentro do bloco, a maior subsequência contígua de
    palavras que NÃO são título nem stopword jurídica/institucional — ou
    None se não houver um núcleo de `min_palavras`+ palavras válido.

    `min_palavras` é 2 por padrão (heurística genérica, para evitar falso
    positivo sobre uma palavra capitalizada solta em qualquer lugar do
    texto). Em contexto já identificado como campo de dado pessoal (ex.:
    valor de um rótulo "Filiação:"/"Nome da Mãe:") usa-se min_palavras=1,
    pois ali o rótulo já garante que se trata de nome de pessoa — inclusive
    quando o OCR degradou o texto e só restou um fragmento de uma palavra
    (ex.: um dos dois nomes truncado/ilegível pelo scanner).

    Isso resolve dois problemas ao mesmo tempo:
      - títulos/cargos (Dr., MM. Juiz, Defensor Público...) ficam de fora
        do rótulo, cobrindo só o nome da pessoa;
      - um bloco só é descartado por conter uma stopword se a stopword
        estiver DENTRO do núcleo remanescente, não em qualquer lugar do
        bloco inteiro (ex.: "Defensor Público Marcos Vinicius Oliveira"
        ainda aproveita "Marcos Vinicius Oliveira").
    """
    tokens = []  # (inicio_no_bloco, fim_no_bloco, palavra)
    for m in re.finditer(r"\S+", bloco):
        tokens.append((m.start(), m.end(), m.group(0)))

    def relevante(tok):
        return tok[2].lower() not in PARTICULAS_NOME

    def e_palavra_curta_demais(palavra):
        # Uma única letra (ex.: sigla solta, ou a "A"/"B" de um artigo de
        # lei como "339-A") não conta como palavra de nome válida.
        return len(_normalizar(palavra)) < 2

    melhor = None
    atual = []
    for tok in tokens:
        _, _, palavra = tok
        if relevante(tok) and (
            _e_titulo(palavra) or _e_stopword_juridica(palavra) or e_palavra_curta_demais(palavra)
        ):
            # corta a sequência aqui
            if atual:
                candidato = atual
                atual = []
                if melhor is None or _comprimento(candidato) > _comprimento(melhor):
                    melhor = candidato
            continue
        atual.append(tok)
    if atual and (melhor is None or _comprimento(atual) > _comprimento(melhor)):
        melhor = atual

    if not melhor:
        return None

    # Remove partículas soltas nas bordas (ex.: bloco terminando em "de")
    while melhor and not relevante(melhor[0]):
        melhor = melhor[1:]
    while melhor and not relevante(melhor[-1]):
        melhor = melhor[:-1]

    palavras_relevantes = [t for t in melhor if relevante(t)]
    if len(palavras_relevantes) < min_palavras:
        return None

    # Nomes reais de pessoa raramente passam de ~6 palavras (nome +
    # múltiplos sobrenomes). Blocos mais longos que isso costumam ser
    # frases inteiras de formulário/relato que escaparam das stopwords
    # (ex.: "SOLICITANTE RELATA QUE OUVIU VÁRIOS DISPAROS DE ARMA DE
    # FOGO") — melhor não anonimizar do que produzir um rótulo que engole
    # uma frase inteira e some conteúdo do relato sem necessidade.
    MAX_PALAVRAS_NOME = 6
    if len(palavras_relevantes) > MAX_PALAVRAS_NOME:
        return None

    inicio = melhor[0][0]
    fim = melhor[-1][1]
    return inicio, fim, bloco[inicio:fim]


def _comprimento(lista_tokens):
    return sum(1 for t in lista_tokens if t[2].lower() not in PARTICULAS_NOME)


class MotorAnonimizacao:
    """
    Detecta e substitui dados pessoais/sigilosos por rótulos padronizados
    (ex.: cpf_1, telefone_1, nome_1, tribunal_1, processo_numero_1...),
    mantendo um registro (mapa) de cada ocorrência com a(s) página(s).
    """

    # Categorias cuja busca precisa ser tolerante a acentuação (o padrão
    # e a comparação usam texto sem acento; a substituição preserva o
    # texto original). "estado"/"municipio" rodam ANTES de "tribunal" de
    # propósito: assim "Tribunal de Justiça do Estado de Alagoas" já
    # chega ao padrão de tribunal como "...do Estado [estado_1]", e o
    # órgão (TJ) continua identificável, só o nome geográfico some.
    CATEGORIAS_TOLERANTES_ACENTO = ["estado", "municipio", "tribunal"]

    # Ordem importa: categorias mais específicas/estruturadas primeiro,
    # para não deixar um regex genérico "roubar" parte de um padrão mais
    # específico (ex.: número de processo antes de telefone).
    CATEGORIAS_REGEX = [
        ("processo_numero", RE_PROCESSO_CNJ),
        ("cnpj", RE_CNPJ),
        ("cpf", RE_CPF),
        ("cep", RE_CEP),
        ("email", RE_EMAIL),
        ("endereco", RE_ENDERECO),
        ("estado", RE_ESTADO),
        ("municipio", RE_MUNICIPIO),
        ("tribunal", TRIBUNAL_PADRAO),
        ("rg", RE_RG),
        ("telefone", RE_TELEFONE),
    ]

    def __init__(self):
        # texto_original_exato -> rotulo (ex.: "João da Silva" -> "nome_3")
        self.mapa_texto_para_rotulo = OrderedDict()
        # categoria -> próximo número disponível
        self.contadores = {}
        # rotulo -> {"categoria":..., "texto_original":..., "paginas": set()}
        self.registro = OrderedDict()

    # Categorias em que a MESMA entidade pode aparecer com grafias
    # diferentes de maiúsculas/minúsculas (ex.: "ALAGOAS" vs "Alagoas",
    # "TRIBUNAL DE JUSTIÇA" vs "Tribunal de Justiça") e por isso devem
    # deduplicar por forma normalizada, não pelo texto exato — senão a
    # mesma entidade ganharia dois rótulos diferentes.
    CATEGORIAS_DEDUP_INSENSIVEL = {"estado", "municipio", "tribunal"}

    def _obter_rotulo(self, categoria: str, texto_original: str) -> str:
        texto_original = texto_original.strip()
        if categoria in self.CATEGORIAS_DEDUP_INSENSIVEL:
            chave = (categoria, _normalizar(texto_original))
        else:
            chave = (categoria, texto_original)
        if chave in self.mapa_texto_para_rotulo:
            return self.mapa_texto_para_rotulo[chave]

        n = self.contadores.get(categoria, 0) + 1
        self.contadores[categoria] = n
        rotulo = f"{categoria}_{n}"
        self.mapa_texto_para_rotulo[chave] = rotulo
        self.registro[rotulo] = {
            "categoria": categoria,
            "texto_original": texto_original.strip(),
            "paginas": set(),
        }
        return rotulo

    def _registrar_ocorrencia(self, rotulo: str, pagina: int):
        self.registro[rotulo]["paginas"].add(pagina)

    def _mascarar_valor_campo_pessoal(self, valor: str, numero_pagina: int) -> str:
        """
        Mascara o valor de um campo já identificado como pessoal (ver
        RE_CAMPO_PESSOAL) segmento a segmento (dividindo por vírgula, barra
        ou "e"/"E", pois um mesmo campo pode trazer dois nomes — ex.: mãe e
        pai). Usa min_palavras=1 (diferente da heurística genérica), porque
        o rótulo do campo já garante que aquilo é nome de pessoa, mesmo que
        o OCR tenha degradado o texto a ponto de sobrar só um fragmento.
        """
        partes = RE_SEPARADOR_NOME_CAMPO.split(valor)
        saida = []
        for parte in partes:
            if RE_SEPARADOR_NOME_CAMPO.fullmatch(parte or ""):
                saida.append(parte)
                continue
            segmento = parte
            if not segmento or not segmento.strip():
                saida.append(segmento)
                continue
            if _normalizar(segmento) in PLACEHOLDERS_NEGATIVOS:
                saida.append(segmento)
                continue
            resultado = _extrair_nucleo_nome(segmento, min_palavras=1)
            if resultado is None:
                saida.append(segmento)
                continue
            inicio, fim, nucleo = resultado
            rotulo = self._obter_rotulo("nome", nucleo)
            self._registrar_ocorrencia(rotulo, numero_pagina)
            saida.append(f"{segmento[:inicio]}[{rotulo}]{segmento[fim:]}")
        return "".join(saida)

    def _mascarar_campos_pessoais(self, texto: str, numero_pagina: int) -> str:
        def _sub_campo(m):
            rotulo_campo, separador, valor = m.group(1), m.group(2), m.group(3)
            valor_mascarado = self._mascarar_valor_campo_pessoal(valor, numero_pagina)
            return f"{rotulo_campo}{separador}{valor_mascarado}"

        return RE_CAMPO_PESSOAL.sub(_sub_campo, texto)

    def processar_pagina(self, texto: str, numero_pagina: int) -> str:
        if not texto:
            return texto

        # 0) Campos rotulados que só podem conter nome de pessoa (Filiação,
        #    Nome da Mãe/Pai, etc.) — roda ANTES da heurística genérica,
        #    com tolerância a fragmentos de 1 palavra (ver
        #    _mascarar_valor_campo_pessoal). Preenche a lacuna que permitia
        #    nome de pai/mãe vazar quando o OCR truncava/corrompia o nome.
        texto = self._mascarar_campos_pessoais(texto, numero_pagina)

        # 1) Categorias estruturadas via regex (CPF, CNPJ, processo, etc.)
        for categoria, padrao in self.CATEGORIAS_REGEX:
            if categoria in self.CATEGORIAS_TOLERANTES_ACENTO:
                # Busca tolerante a acentuação: o padrão está escrito sem
                # acento; comparamos contra uma versão do texto sem
                # acento (mesmo comprimento, então os índices batem 1:1),
                # mas substituímos usando o texto ORIGINAL, preservando
                # acentuação de tudo que não for substituído.
                texto_sem_acento = _remover_acentos(texto)
                partes = []
                cursor = 0
                for m in padrao.finditer(texto_sem_acento):
                    # Caso especial: "Pará"/"PARA" só é tratado como
                    # estado se houver contexto geográfico próximo —
                    # evita confundir com a preposição "para" (ver
                    # _tem_contexto_geografico).
                    if categoria == "estado" and m.group(0).upper() == "PARA":
                        if not _tem_contexto_geografico(texto_sem_acento, m.start(), m.end()):
                            continue
                    original = texto[m.start():m.end()]
                    rotulo = self._obter_rotulo(categoria, original)
                    self._registrar_ocorrencia(rotulo, numero_pagina)
                    partes.append(texto[cursor:m.start()])
                    partes.append(f"[{rotulo}]")
                    cursor = m.end()
                partes.append(texto[cursor:])
                texto = "".join(partes)
                continue

            def _sub(m, categoria=categoria):
                original = m.group(0)
                rotulo = self._obter_rotulo(categoria, original)
                self._registrar_ocorrencia(rotulo, numero_pagina)
                return f"[{rotulo}]"
            texto = padrao.sub(_sub, texto)

        # 2) Nomes com título/pronome de tratamento (Dr., MM. Juiz, etc.)
        #    e (3) nomes próprios genéricos (heurística: bloco de palavras
        #    capitalizadas) usam a mesma lógica de extração de núcleo, que
        #    descarta o título/cargo e quaisquer stopwords institucionais,
        #    preservando o restante do texto intacto.
        def _sub_bloco(m):
            bloco = m.group(0)
            resultado = _extrair_nucleo_nome(bloco)
            if resultado is None:
                return bloco
            inicio, fim, nucleo = resultado
            rotulo = self._obter_rotulo("nome", nucleo)
            self._registrar_ocorrencia(rotulo, numero_pagina)
            return f"{bloco[:inicio]}[{rotulo}]{bloco[fim:]}"

        texto = RE_TITULO_NOME.sub(_sub_bloco, texto)
        texto = RE_BLOCO_MAIUSCULO.sub(_sub_bloco, texto)
        texto = RE_BLOCO_CAIXA_ALTA.sub(_sub_bloco, texto)

        return texto

    def gerar_markdown_chave(self, referencia: str, total_paginas: int) -> str:
        linhas = [
            f"<!-- Chave de desanonimização | Referência: {referencia} | {total_paginas} páginas -->",
            "",
            "# Chave de Desanonimização",
            "",
            "Este arquivo relaciona cada dado anonimizado no `.md` principal com o",
            "texto original substituído e a(s) página(s) em que ele ocorre no PDF de",
            "origem. Mantenha este arquivo em local seguro/restrito — ele reverte a",
            "anonimização.",
            "",
            "Para reverter a anonimização automaticamente, salve este arquivo junto",
            "com o `.md` anonimizado correspondente na pasta",
            "`arquivos_de_entrada/desanonimizacao/` do pipeline automatizado",
            "(`auto_conversor.py`). O script identifica sozinho qual chave pertence",
            "a qual documento (mesmo com vários pares anexados de uma vez) e gera",
            "o arquivo já revertido em `arquivos_convertidos/desanonimizacao/`.",
            "",
            "Gerado automaticamente por heurística (ver observações de limitação no",
            "topo do script `pdf_to_md_anonimizado.py`). Revise antes de considerar",
            "a anonimização completa, especialmente em processos sob segredo de",
            "justiça.",
            "",
        ]

        if not self.registro:
            linhas.append("*Nenhum dado foi anonimizado neste documento.*")
            return "\n".join(linhas)

        # Agrupa por categoria para leitura mais organizada
        por_categoria = OrderedDict()
        for rotulo, info in self.registro.items():
            por_categoria.setdefault(info["categoria"], []).append((rotulo, info))

        nomes_categoria = {
            "processo_numero": "Números de Processo",
            "cnpj": "CNPJ",
            "cpf": "CPF",
            "cep": "CEP",
            "email": "E-mail",
            "endereco": "Endereços",
            "estado": "Estado",
            "municipio": "Município",
            "tribunal": "Tribunal / Vara / Comarca",
            "rg": "RG",
            "telefone": "Telefone",
            "nome": "Nomes de Pessoas",
        }

        for categoria, itens in por_categoria.items():
            titulo = nomes_categoria.get(categoria, categoria.capitalize())
            linhas.append(f"## {titulo}")
            linhas.append("")
            for rotulo, info in itens:
                paginas_str = ", ".join(str(p) for p in sorted(info["paginas"]))
                # Um item embaixo do outro (não em tabela): o texto
                # original pode ter várias linhas ou ser longo, e uma
                # tabela Markdown de linha única fica ilegível nesses
                # casos — lado a lado e cortando a leitura.
                texto_original = info["texto_original"].replace("\n", " ").strip()
                linhas.append(f"{rotulo} → {texto_original}")
                linhas.append(f"Páginas: {paginas_str}")
                linhas.append("")

        return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Orquestração: extrai, anonimiza, grava os dois .md
# ---------------------------------------------------------------------------

def gerar_referencia(caminho_pdf: Path) -> str:
    """
    Gera um identificador ANÔNIMO para nomear os arquivos de saída,
    deliberadamente SEM usar o nome do arquivo de entrada (que pode
    conter nome de partes, número de processo etc.).

    Formato: AAAA-MM-DD_ref-XXXXXX
    - a data é a do momento da conversão;
    - o código de 6 caracteres é um hash (sha256) do CONTEÚDO em bytes do
      PDF — não do nome do arquivo, não de dados pessoais nele extraídos.
      Isso faz com que o mesmo PDF gere sempre o mesmo código (útil para
      saber se aquele documento já foi convertido antes), enquanto o
      nome do arquivo original nunca aparece na saída.
    """
    data_str = datetime.now().strftime("%Y-%m-%d")
    conteudo_bytes = caminho_pdf.read_bytes()
    hash_completo = hashlib.sha256(conteudo_bytes).hexdigest()
    codigo = hash_completo[:6]
    return f"{data_str}_ref-{codigo}"


def converter_pdf_anonimizado(caminho_pdf: Path, pasta_saida: Path, forcar_ocr: bool,
                                idioma: str, verbose=True):
    paginas, paginas_com_ocr, total_paginas = extrair_paginas(
        caminho_pdf, forcar_ocr, idioma, verbose=verbose
    )

    motor = MotorAnonimizacao()
    blocos = []

    for numero_pagina, texto in paginas:
        texto_anonimizado = motor.processar_pagina(texto, numero_pagina)
        if not texto_anonimizado:
            texto_anonimizado = "*(nenhum texto extraído nesta página)*"
        blocos.append(f"## Página {numero_pagina}\n\n{texto_anonimizado}\n")

    referencia = gerar_referencia(caminho_pdf)
    caminho_saida = pasta_saida / f"projeto_{referencia}.md"
    caminho_chave = pasta_saida / f"chave_de_desanonimizacao_{referencia}.md"

    cabecalho = (
        f"<!-- Documento anonimizado | Referência: {referencia} | "
        f"{total_paginas} páginas -->\n\n"
        "<!-- Anonimização automática por padrões/heurística. Consulte o "
        f"arquivo chave_de_desanonimizacao_{referencia}.md antes de considerar "
        "este texto seguro para envio externo. O nome do arquivo de origem "
        "foi deliberadamente omitido desta saída. -->\n\n"
    )
    conteudo_final = cabecalho + "\n---\n\n".join(blocos)
    caminho_saida.write_text(conteudo_final, encoding="utf-8")

    conteudo_chave = motor.gerar_markdown_chave(referencia, total_paginas)
    caminho_chave.write_text(conteudo_chave, encoding="utf-8")

    if verbose:
        print(f"\n✔ Gerado (anonimizado): {caminho_saida.name}")
        print(f"✔ Gerado (chave de desanonimização): {caminho_chave.name}")
        if paginas_com_ocr:
            print(f"  Páginas que precisaram de OCR: {paginas_com_ocr}")
        total_itens = len(motor.registro)
        print(f"  Total de itens anonimizados: {total_itens}")

    return caminho_saida, caminho_chave


def main():
    parser = argparse.ArgumentParser(
        description="Converte PDF em Markdown com marcação de página, ANONIMIZANDO dados pessoais/sigilosos."
    )
    parser.add_argument("pdfs", nargs="+", help="Um ou mais arquivos PDF de entrada")
    parser.add_argument("--pasta-saida", help="Pasta onde salvar os .md gerados (padrão: mesma pasta do PDF de entrada)")
    parser.add_argument("--forcar-ocr", action="store_true", help="Ignora o texto nativo e usa OCR em todas as páginas")
    parser.add_argument("--idioma", default="por", help="Idioma do OCR no formato do Tesseract (padrão: por)")
    args = parser.parse_args()

    for caminho_str in args.pdfs:
        caminho_pdf = Path(caminho_str)
        if not caminho_pdf.exists():
            print(f"Erro: arquivo não encontrado: {caminho_pdf}", file=sys.stderr)
            continue

        pasta_saida = Path(args.pasta_saida) if args.pasta_saida else caminho_pdf.parent
        pasta_saida.mkdir(parents=True, exist_ok=True)

        print(f"Convertendo e anonimizando: {caminho_pdf.name}")
        converter_pdf_anonimizado(caminho_pdf, pasta_saida, args.forcar_ocr, args.idioma)
        print()


if __name__ == "__main__":
    main()
