# Conversor de PDF/Imagem para Markdown, com OCR e Anonimização

Converte PDFs (nativos ou escaneados) — e também imagens soltas — em
Markdown com marcação de página (`## Página N`), aplicando OCR
automaticamente nas páginas que forem imagem, e com um modo dedicado de
**anonimização de dados pessoais/sigilosos**, em linha com o espírito da
**Resolução CNJ nº 615/2025** (art. 7º, §2º; art. 19, §3º, IV; art. 30 e
§1º), que exige anonimização/pseudonimização "na origem" de dados
pessoais e sigilosos antes de submetê-los a ferramentas de inteligência
artificial externas.

Não depende de nenhum serviço externo: tudo roda localmente, usando
[Tesseract OCR](https://github.com/tesseract-ocr/tesseract) e,
opcionalmente, [OCRmyPDF](https://ocrmypdf.readthedocs.io/) para scans
difíceis (tortos, rotacionados, ruidosos).

## Sumário

1. [Estrutura de pastas do projeto](#1-estrutura-de-pastas-do-projeto)
2. [Instalação](#2-instalação)
3. [Uso automatizado — fila de pastas (`auto_conversor.py`)](#3-uso-automatizado--fila-de-pastas-auto_conversorpy)
4. [Uso pontual — um arquivo por vez (`pdf_to_md.py` / `pdf_to_md_anonimizado.py`)](#4-uso-pontual--um-arquivo-por-vez-pdf_to_mdpy--pdf_to_md_anonimizadopy)
5. [Como funciona o OCR (texto nativo, fallback e OCRmyPDF)](#5-como-funciona-o-ocr-texto-nativo-fallback-e-ocrmypdf)
6. [Como funciona a anonimização](#6-como-funciona-a-anonimização)
7. [O arquivo de chave de desanonimização](#7-o-arquivo-de-chave-de-desanonimização)
8. [Revertendo a anonimização (desanonimização)](#8-revertendo-a-anonimização-desanonimização)
9. [Configuração no Windows](#9-configuração-no-windows)
10. [Licença](#10-licença)

---

## 1. Estrutura de pastas do projeto

```
12-conversoes-pdf-md/
├── scripts/                     <- todos os scripts e esta documentação
│   ├── auto_conversor.py        <- pipeline automatizado (fila de pastas)
│   ├── executar_conversor.sh    <- atalho de linha de comando (Linux/macOS)
│   ├── pdf_to_md.py             <- conversão pontual, sem anonimização
│   ├── pdf_to_md_anonimizado.py <- conversão pontual, COM anonimização
│   ├── LICENSE
│   └── LEIA-ME.md               <- este arquivo
├── arquivos_de_entrada/         <- pastas de entrada do modo automatizado
│   ├── padrao/
│   ├── ocr/
│   ├── anonimizacao/
│   └── desanonimizacao/
├── arquivos_convertidos/        <- saída do modo automatizado (por data)
│   ├── padrao/AAAA-MM-DD/
│   ├── ocr/AAAA-MM-DD/
│   ├── anonimizacao/AAAA-MM-DD/
│   └── desanonimizacao/AAAA-MM-DD/<nome>/
└── log/                         <- log diário e progresso do modo automatizado
```

Existem **dois jeitos de usar** este projeto, independentes entre si:

- **Automatizado, por fila de pastas** (`auto_conversor.py` /
  `executar_conversor.sh`): você solta o arquivo em
  `arquivos_de_entrada/<modo>/`, roda um comando, e o resultado (já
  organizado por data, com rastreabilidade e log) aparece em
  `arquivos_convertidos/<modo>/AAAA-MM-DD/`. Bom para uso recorrente e
  para lotes de documentos.
- **Pontual, um arquivo por vez** (`pdf_to_md.py` /
  `pdf_to_md_anonimizado.py` chamados diretamente): você indica o PDF e
  onde salvar o `.md`, sem depender da estrutura de pastas acima. Bom
  para uso avulso ou quando o projeto é usado como script solto (fora
  desta estrutura de pastas).

Ambos os modos compartilham exatamente a mesma lógica de decisão de OCR e
o mesmo motor de anonimização — `auto_conversor.py` importa
`pdf_to_md_anonimizado.py` como módulo para anonimizar, em vez de
duplicar essa lógica.

---

## 2. Instalação

### 2.1. Linux (Ubuntu/Debian)

```bash
# Tesseract (motor de OCR) + Poppler (renderiza páginas de PDF como imagem)
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-por poppler-utils

# Bibliotecas Python
pip install --user pypdf pdf2image pytesseract pillow pymupdf

# Opcional, mas recomendado: OCRmyPDF, para scans difíceis (tortos, rotacionados, ruidosos)
sudo apt install -y ocrmypdf
```

- `tesseract-ocr` → o programa que "lê" texto em imagens.
- `tesseract-ocr-por` → pacote de idioma português para o OCR (sem ele, o
  OCR erra muito em textos em português).
- `poppler-utils` → transforma páginas do PDF em imagens antes do OCR.
- `pymupdf` → motor de leitura de PDF mais rápido, usado pelo pipeline
  automatizado (`auto_conversor.py`); os scripts pontuais funcionam com
  `pypdf` mesmo sem ele.
- `ocrmypdf` → **opcional**. Sem ele, tudo funciona normalmente (cai no
  fallback de Tesseract puro a 300 DPI); com ele, scans de baixa
  qualidade são corrigidos (deskew, rotação, limpeza de ruído) antes do
  OCR, o que melhora bastante o resultado nesses casos.

Se aparecer erro do tipo "externally-managed-environment" no `pip`:

```bash
pip install --user --break-system-packages pypdf pdf2image pytesseract pillow pymupdf
```

Confirme que tudo foi instalado:

```bash
python3 -c "import pypdf, pdf2image, pytesseract, PIL; print('OK, tudo instalado')"
tesseract --version
ocrmypdf --version   # opcional
```

### 2.2. Windows

Ver seção [9. Configuração no Windows](#9-configuração-no-windows).

---

## 3. Uso automatizado — fila de pastas (`auto_conversor.py`)

### 3.1. Fluxo de trabalho

Basta depositar o arquivo na pasta correspondente ao modo desejado dentro
de `arquivos_de_entrada/`:

| Pasta de entrada | Modo | Destino da conversão |
| :--- | :--- | :--- |
| `arquivos_de_entrada/padrao/` | **Padrão** — extrai texto nativo em alta velocidade via PyMuPDF. Páginas escaneadas/imagem (< 25 caracteres de texto nativo) passam primeiro pelo pré-processamento **OCRmyPDF** híbrido (`--skip-text`: deskew + rotação + limpeza só nessas páginas, preservando intacto o texto nativo das demais) e só caem no Tesseract puro sem pré-processamento se o OCRmyPDF não estiver disponível. | `arquivos_convertidos/padrao/AAAA-MM-DD/` |
| `arquivos_de_entrada/ocr/` | **OCR Otimizado (Estratégia 2)** — processa com OCRmyPDF aplicando deskew, auto-rotação e limpeza de ruído, com OCR **forçado** (`--force-ocr`) em TODAS as páginas, mesmo as que já têm texto nativo. Sem OCRmyPDF disponível, cai automaticamente no fallback via PyMuPDF + Tesseract 300 DPI. | `arquivos_convertidos/ocr/AAAA-MM-DD/` |
| `arquivos_de_entrada/anonimizacao/` | **Anonimização (Res. CNJ nº 615/2025)** — usa o mesmo pré-processamento híbrido do modo Padrão (essencial aqui: um scan torto/ruidoso sem OCR efetivo é a causa mais comum de dado pessoal não detectado, já que a anonimização não consegue mascarar texto que o OCR nunca extraiu) e depois oculta CPF, CNPJ, número de processo, endereços, partes e demais dados sensíveis, gerando o `.md` anonimizado e a `chave_de_desanonimizacao_*.md` de conferência. | `arquivos_convertidos/anonimizacao/AAAA-MM-DD/` |
| `arquivos_de_entrada/desanonimizacao/` | **Desanonimização** — solte aqui o documento anonimizado junto com sua `chave_de_desanonimizacao_*.md` correspondente; o script casa os dois sozinho (mesmo com vários pares juntos) e gera o texto revertido. | `arquivos_convertidos/desanonimizacao/AAAA-MM-DD/<nome>/` (pasta com o documento, a chave e o `desanonimizado_*.md` gerado) |

### 3.2. O que acontece automaticamente em cada conversão

1. **Pasta do dia:** cria automaticamente a subpasta `AAAA-MM-DD` dentro
   de `arquivos_convertidos/<modo>/`.
2. **Markdown com rastreabilidade:** cada página recebe a marcação
   `## Página N` (ou `## Página N (OCR Otimizado - OCRmyPDF)` quando
   aplicável). O `.md` traz cabeçalho com nome do arquivo original,
   modalidade, motor utilizado, data/hora, total de páginas, páginas
   processadas via OCR e hash SHA-256 para conferência.
3. **Transporte seguro do original:** o PDF/imagem de entrada é movido de
   `arquivos_de_entrada/<modo>/` para a pasta do dia em
   `arquivos_convertidos/<modo>/AAAA-MM-DD/`, ao lado do `.md` gerado —
   mantendo a pasta de entrada limpa.
4. **Log diário:** grava um relatório estruturado de todas as conversões
   (sucesso ou falha) em `log/AAAA-MM-DD/conversoes_AAAA-MM-DD.log`.

### 3.3. Comandos

```bash
# Processa uma vez tudo o que estiver pendente nas 4 pastas de entrada
./scripts/executar_conversor.sh
# equivalente a: python3 scripts/auto_conversor.py

# Modo vigilância contínua (converte assim que um arquivo é solto na pasta)
./scripts/executar_conversor.sh watch

# Acompanhar o progresso de uma conversão em andamento
./scripts/executar_conversor.sh progresso

# Ver status das filas (pendentes e já processados), sem processar nada
./scripts/executar_conversor.sh status
```

---

## 4. Uso pontual — um arquivo por vez (`pdf_to_md.py` / `pdf_to_md_anonimizado.py`)

Quando não quiser usar a estrutura de pastas do modo automatizado, chame
os scripts diretamente sobre um arquivo:

```bash
# Conversão simples, sem anonimização
python3 scripts/pdf_to_md.py meu_arquivo.pdf
python3 scripts/pdf_to_md.py meu_arquivo.pdf -o resultado.md
python3 scripts/pdf_to_md.py *.pdf                      # vários de uma vez
python3 scripts/pdf_to_md.py meu_arquivo.pdf --forcar-ocr
python3 scripts/pdf_to_md.py meu_arquivo.pdf --idioma eng

# Conversão COM anonimização automática
python3 scripts/pdf_to_md_anonimizado.py meu_processo.pdf
python3 scripts/pdf_to_md_anonimizado.py meu_processo.pdf --pasta-saida ./anonimizados
python3 scripts/pdf_to_md_anonimizado.py *.pdf
python3 scripts/pdf_to_md_anonimizado.py meu_processo.pdf --forcar-ocr
```

**Qual script chamar:**

- `pdf_to_md.py` — PDF genérico, sem dados pessoais de processo real
  (ex.: doutrina, súmula, material de curso).
- `pdf_to_md_anonimizado.py` — qualquer peça processual real, boletim de
  ocorrência, decisão ou documento com dados de um caso concreto. Gera
  dois arquivos: o `.md` anonimizado e a
  `chave_de_desanonimizacao_*.md` (ver seção 7).

Nenhum dos dois scripts move, apaga ou sobrescreve o arquivo de origem —
só leem e gravam um `.md` novo em outro lugar.

---

## 5. Como funciona o OCR (texto nativo, fallback e OCRmyPDF)

Para cada página do documento:

1. Tenta extrair o texto nativo primeiro (quando o PDF já tem texto
   selecionável) — nenhuma imagem é gerada, nenhum OCR roda.
2. Se o texto nativo tiver menos de 25 caracteres (constante
   `MIN_CHARS_TEXTO_NATIVO`), a página é tratada como escaneada/imagem:
   - **Com OCRmyPDF disponível:** a página passa primeiro por
     deskew + correção de rotação + limpeza de ruído antes do OCR — é o
     que resolve a maioria dos scans tortos, rotacionados ou ruidosos.
     No modo automatizado "Padrão"/"Anonimização" isso roda em modo
     híbrido (`--skip-text`: só mexe nas páginas sem texto, preservando
     as demais); no modo "OCR"/`--forcar-ocr` roda forçado
     (`--force-ocr`) em todas as páginas.
   - **Sem OCRmyPDF:** cai no fallback de Tesseract puro a 300 DPI,
     página a página, sem pré-processamento.
3. Isso é decidido página por página, dentro do mesmo documento — um PDF
   com páginas digitadas e páginas escaneadas misturadas é tratado
   corretamente, sem intervenção manual.

No fim, o terminal (e o cabeçalho do `.md`) mostram quais páginas
precisaram de OCR — vale conferir essas páginas quando o documento for
crítico, já que OCR raramente é 100% perfeito.

---

## 6. Como funciona a anonimização

Aplicável a `pdf_to_md_anonimizado.py` e ao modo `anonimizacao` do
`auto_conversor.py` (mesmo motor, chamado como módulo).

### O que é detectado e anonimizado

- Nome do estado (`estado_1`...) e do município/capital (`municipio_1`...)
  — inclusive DENTRO do nome de um órgão (ex.: "Governo do Estado de
  Alagoas" → "Governo do Estado [estado_1]"): o órgão continua
  identificável, só o nome geográfico fica oculto.
- Tipo de tribunal, vara, comarca ou fórum (`tribunal_1`...) — só o
  "tipo" do órgão vira rótulo (TJ, STJ, Vara Criminal, Comarca...); o
  nome do estado/cidade dentro dele já foi tratado pela categoria acima.
- Número de processo, padrão CNJ (`processo_numero_1`...)
- CPF (`cpf_1`...), CNPJ (`cnpj_1`...), RG (`rg_1`...)
- Telefones (`telefone_1`...), e-mails (`email_1`...)
- Endereços — Rua/Av./Alameda etc. com número (`endereco_1`...)
- CEP (`cep_1`...)
- Nomes de pessoas — partes, vítimas, testemunhas, juízes, promotores,
  defensores, delegados, advogados, servidores (`nome_1`, `nome_2`...),
  reconhecidos tanto em Capitalização Normal quanto TODO EM CAIXA ALTA.
- Nomes em **campos rotulados** de formulário/BO — "Filiação:", "Nome da
  Mãe:", "Nome do Pai:", "Genitor(a):", "Nome do(a) Declarante:", etc. —
  são mascarados mesmo quando o OCR degrada o nome a um único fragmento
  de palavra (o rótulo do campo já garante que aquilo é nome de pessoa,
  então não é exigido o mínimo de 2 palavras "limpas" da heurística
  genérica abaixo).

Cada tipo de dado recebe um rótulo sequencial próprio, na ordem em que
aparece no documento — a MESMA entidade (ex.: "Alagoas" e "ALAGOAS")
sempre recebe o mesmo rótulo, mesmo grafada de formas diferentes ao longo
do documento. O nome do arquivo PDF de origem também não é usado para
nomear a saída (ver seção 7), já que ele mesmo poderia identificar o
processo.

**Nota sobre "Pará":** por coincidir com a preposição "para", o estado do
Pará só é anonimizado com um contexto geográfico claro ao lado (ex.:
"Estado do Pará", "Belém/PA"). Os outros 26 estados não têm esse
problema.

### Como nomes de pessoas são detectados (heurística, não é infalível)

Diferente de CPF/telefone/processo — formato fixo, alta confiabilidade —
nomes de pessoas não têm padrão fixo. A heurística usa:

- sequências de palavras capitalizadas (Normal ou TODO EM CAIXA ALTA);
- nomes precedidos de título/cargo ("Dr.", "MM. Juiz", "Delegado"...) —
  o título é descartado, só a pessoa vira rótulo;
- uma lista extensa de stopwords institucionais/jurídicas/de formulário
  ("Ministério Público", "Data de Nascimento", "Instituto Médico
  Legal"...) para não confundir essas expressões com nomes;
- limite de 6 palavras por bloco (nomes reais raramente passam disso;
  blocos maiores costumam ser frases de relato inteiras);
- para campos já rotulados como pessoais (Filiação etc.), tolerância a
  fragmento de 1 palavra (ver seção acima).

**Isso funciona bem na maioria dos casos, mas pode falhar:** um nome fora
do padrão pode passar sem ser anonimizado (falso negativo), ou uma
expressão pode ser anonimizada por engano (falso positivo — nesse caso
só sobra um rótulo a mais, sem comprometer o sigilo de ninguém).

**Por isso, sempre revise a chave de desanonimização (seção 7) antes de
considerar o `.md` anonimizado seguro para envio a qualquer ferramenta
externa, especialmente em processos sob segredo de justiça.** Este script
é uma ferramenta de apoio, não substitui o julgamento humano sobre o que
é sigiloso naquele processo específico.

---

## 7. O arquivo de chave de desanonimização

Para não correr o risco de o próprio **nome do arquivo** revelar o
processo, a saída usa um nome genérico baseado em data e um código de
referência curto:

```
projeto_2026-09-07_ref-a1b2c3.md                  <- texto anonimizado
chave_de_desanonimizacao_2026-09-07_ref-a1b2c3.md <- chave (mesma referência)
```

- A data é a do dia da conversão.
- O código (`a1b2c3`) vem do conteúdo do PDF (não do nome do arquivo nem
  de dado pessoal extraído) — o mesmo PDF sempre gera o mesmo código.
- O prefixo `chave_de_desanonimizacao_` mais a referência compartilhada é
  o que permite ao `auto_conversor.py` casar chave e documento
  automaticamente (seção 8).

A chave lista, para cada rótulo usado, o texto original substituído e a(s)
página(s) em que aparece:

```
## Nomes de Pessoas

nome_1 → Carlos Eduardo Ramos
Páginas: 1

nome_2 → Antonio Marques dos Santos
Páginas: 1
```

**Esse arquivo reúne todos os dados sensíveis do processo em um só
lugar — trate-o com o mesmo cuidado (ou mais) que o PDF original.**
Guarde-o só para você (ou para quem tiver acesso autorizado ao
processo); é o `.md` SEM o prefixo `chave_de_desanonimizacao_` que pode
ser levado para pesquisa em ferramentas de IA externas.

---

## 8. Revertendo a anonimização (desanonimização)

Solte o documento anonimizado **junto com sua chave**:

- Modo automatizado: em `arquivos_de_entrada/desanonimizacao/`, depois
  rode `./scripts/executar_conversor.sh`. O resultado sai em
  `arquivos_convertidos/desanonimizacao/AAAA-MM-DD/<nome>/`, com os três
  arquivos lado a lado (documento anonimizado, chave, e o
  `desanonimizado_*.md` já revertido).
- O script casa sozinho qual chave pertence a qual documento (pelo
  código `ref-XXXXXX` compartilhado no nome de ambos), mesmo com vários
  pares soltos juntos de uma vez.

---

## 9. Configuração no Windows

Duas rotas, dependendo da sua situação:

- **Opção A** — você PODE instalar programas (Python) no Windows.
- **Opção B** — máquina corporativa travada, sem autorização para
  instalar nada.

### Opção A — Com Python (recomendada)

1. Baixe o Python em https://www.python.org/downloads/windows/ e, no
   instalador, **marque "Add Python to PATH"**.
2. Confirme no Prompt de Comando: `python --version`.
3. Instale as bibliotecas:
   ```cmd
   pip install pypdf pdf2image pytesseract pillow pymupdf
   ```
4. Instale o **Tesseract OCR**:
   - Baixe em https://github.com/UB-Mannheim/tesseract/wiki
     (`tesseract-ocr-w64-setup-...exe`).
   - Durante a instalação, marque o pacote de idioma **Portuguese**.
5. Instale o **Poppler**:
   - Baixe o `.zip` mais recente em
     https://github.com/oschwartz10612/poppler-windows/releases,
     extraia e adicione a subpasta `Library\bin` ao PATH do Windows.
6. (Opcional, para scans difíceis) Instale o **OCRmyPDF** e o
   **Ghostscript**, necessários para a Estratégia 2:
   ```cmd
   winget install ArtifexSoftware.Ghostscript
   pip install ocrmypdf
   ```
   Sem eles, o script ativa **automaticamente o fallback** de
   PyMuPDF + Tesseract 300 DPI, convertendo normalmente sem interrupções.
7. Baixe o modelo treinado em português (`por.traineddata`) para a pasta
   `tessdata` do Tesseract, caso não tenha marcado o pacote de idioma no
   passo 4.

### Opção B — Sem poder instalar nada

Sem Python/Tesseract/Poppler instaláveis, este pipeline não roda
localmente no Windows. Peça a quem administra a máquina para liberar a
instalação, ou rode a conversão em outra máquina (Linux/macOS, ou um
Windows onde a Opção A seja possível) e transfira só o `.md` resultante.

---

## 10. Licença

Copyright (C) 2026 Domingos José de Souza Lima Júnior.

Distribuído sob a licença **GNU General Public License v3.0 (GPLv3)**.
Veja o arquivo `LICENSE` nesta mesma pasta para os termos completos. O
cabeçalho de copyright e a nota de licença também constam no topo de cada
script.
