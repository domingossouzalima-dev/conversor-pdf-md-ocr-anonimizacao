# conversor-pdf-md-ocr-anonimizacao

Conjunto de scripts em Python para converter PDFs (nativos ou escaneados) em
Markdown, com marcação de página, fallback automático de OCR e um modo
dedicado de **anonimização de dados pessoais/sigilosos**, direto na
conversão.

Não depende de nenhum serviço externo: tudo roda localmente, usando
[Tesseract OCR](https://github.com/tesseract-ocr/tesseract) e, opcionalmente,
[OCRmyPDF](https://ocrmypdf.readthedocs.io/).

## Por que existe

PDFs escaneados (imagem) não têm texto selecionável, o que atrapalha buscas,
citação de página e uso do conteúdo em outras ferramentas (inclusive
assistentes de IA). Este projeto resolve isso convertendo qualquer PDF —
digital ou escaneado — em um `.md` com texto pesquisável, marcando de qual
página do PDF original cada trecho veio.

## Funcionalidades

- **Extração de texto nativo primeiro.** Se o PDF já tem texto selecionável,
  ele é extraído diretamente — nenhuma imagem é gerada, nenhum OCR roda.
- **OCR automático como fallback.** Páginas sem texto suficiente (tipicamente
  páginas escaneadas) são renderizadas como imagem a 300 DPI e processadas
  pelo Tesseract. Isso acontece por página, então um PDF pode ter páginas
  digitais e páginas escaneadas misturadas sem problema.
- **OCR otimizado opcional via OCRmyPDF.** Quando o OCR é forçado em um
  documento inteiro, o pipeline tenta primeiro o `OCRmyPDF`, que aplica
  correção de rotação, correção de inclinação (deskew) e limpeza de ruído
  antes do OCR — melhorando a qualidade em documentos mal escaneados. Se o
  `OCRmyPDF` não estiver instalado, cai automaticamente para o método manual
  (renderização a 300 DPI + Tesseract puro).
- **Anonimização automática opcional.** Um motor baseado em regex e
  heurística de nomes próprios detecta e substitui CPF, CNPJ, número de
  processo (padrão CNJ), CEP, e-mail, telefone, RG, endereço, nomes de
  estado/município e nomes de pessoas por rótulos como `[cpf_1]`,
  `[nome_2]`. Gera também uma "chave de desanonimização" separada, com a
  correspondência rótulo → texto original, para conferência humana.
- **Desanonimização automática.** Basta soltar o documento anonimizado
  junto com sua chave na pasta de entrada correspondente: o pipeline casa
  os dois sozinho (mesmo com vários pares anexados de uma vez) e gera o
  texto já revertido.
- **Rastreabilidade.** O pipeline automatizado registra hash SHA-256 do
  arquivo original, motor usado, páginas que precisaram de OCR e tempo de
  conversão — tanto no cabeçalho do `.md` gerado quanto em log diário.
- **Multiplataforma.** Testado em Linux; inclui detecção automática do
  executável do Tesseract no Windows.

## Como funciona (visão geral)

```
PDF de entrada
     │
     ▼
Para cada página: existe texto nativo suficiente (≥ 25 caracteres)?
     │                                   │
    sim                                  não
     │                                   │
     ▼                                   ▼
usa o texto extraído          renderiza a página como imagem (300 DPI)
     │                         e roda OCR (Tesseract, ou OCRmyPDF quando
     │                         o OCR é forçado no documento inteiro)
     │                                   │
     └───────────────┬───────────────────┘
                      ▼
        bloco "## Página N" no .md de saída
                      │
                      ▼
        (opcional) anonimização de dados pessoais/sigilosos
```

Importante: a conversão nunca "melhora o PPI/DPI de um PDF existente". O que
acontece é uma **rasterização sob demanda**: só quando uma página não tem
texto extraível, ela é transformada em uma imagem nova a 300 DPI (resolução
recomendada para boa acurácia do Tesseract) e essa imagem, sim, passa pelo
OCR. Páginas com texto nativo nunca viram imagem.

## Estrutura do repositório

As quatro pastas de entrada (`material/padrao/`, `material/ocr/`,
`material/anonimizacao/` e `material/desanonimizacao/`) **já vêm criadas
neste repositório** (mantidas no Git por um `.gitkeep`) — basta clonar ou
copiar a pasta inteira para o seu sistema, sem precisar criar nada à mão.
As pastas de saída (`conversoes/` e `log/`) **não** vêm no repositório:
o próprio script as cria automaticamente na primeira execução, cada uma
já com a subpasta do dia (`AAAA-MM-DD`).

```
.
├── scripts/
│   ├── pdf_to_md.py              # conversor standalone (uso pontual, um PDF por vez)
│   ├── pdf_to_md_anonimizado.py  # conversor standalone + anonimização
│   ├── auto_conversor.py         # pipeline automatizado com filas e rastreabilidade
│   └── executar_conversor.sh     # atalho de linha de comando para o pipeline
├── material/                     # pastas de ENTRADA do pipeline automatizado (já criadas)
│   ├── padrao/                   # PDFs para conversão normal (texto nativo + OCR se preciso)
│   ├── ocr/                      # PDFs para OCR forçado em todas as páginas
│   ├── anonimizacao/             # PDFs para conversão com anonimização
│   └── desanonimizacao/          # documento anonimizado + chave, para reverter
├── conversoes/                   # pastas de SAÍDA (criadas automaticamente, por data)
├── log/                          # logs e progresso (criados automaticamente)
├── requirements.txt
├── LICENSE
└── README.md
```

A relação é simples: **cada subpasta de `material/` tem uma subpasta
correspondente em `conversoes/`**, com o mesmo nome. Você solta o arquivo
na pasta de entrada que representa o comportamento que quer (padrão, OCR
forçado, anonimização, ou desanonimização); o script processa e grava o
resultado na pasta de saída equivalente, dentro de uma subpasta com a
data do dia (`AAAA-MM-DD`). A única exceção é `desanonimizacao/`, cuja
saída é organizada por documento em vez de simplesmente por data — veja a
seção [Desanonimização](#desanonimização-revertendo-o-documento) abaixo.

## Os dois modos de uso

### 1. Scripts standalone — `pdf_to_md.py` e `pdf_to_md_anonimizado.py`

Para converter um PDF pontual, sem pipeline nem pastas fixas. Você aponta
para o arquivo e recebe o `.md` na hora.

### 2. Pipeline automatizado — `auto_conversor.py`

Para quem converte documentos com frequência. Você solta arquivos nas pastas
de `material/` e roda o script (ou deixa em modo vigilância contínua); ele
processa tudo, organiza a saída por data e mantém log e hash de cada
conversão.

## Instalação

### Dependências de sistema

**Linux (Debian/Ubuntu):**

```bash
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-por poppler-utils
```

- `tesseract-ocr` — motor de OCR.
- `tesseract-ocr-por` — pacote de idioma português (troque/adicione o pacote
  do idioma que precisar; o padrão do script é `por`).
- `poppler-utils` — necessário para o fallback de renderização de página via
  `pdf2image`.

Opcional, para OCR otimizado com deskew/limpeza automática:

```bash
sudo apt install -y ocrmypdf
# ou: pip install --user ocrmypdf
```

**Windows:** instale o [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)
(mantenha o instalador padrão, que o script já procura automaticamente) e o
[Poppler para Windows](https://github.com/oschwartz10612/poppler-windows).

### Dependências Python

```bash
pip install -r requirements.txt
```

Se aparecer erro de "externally-managed-environment" no Linux:

```bash
pip install --user --break-system-packages -r requirements.txt
```

## Uso

### Converter um PDF pontual

```bash
python3 scripts/pdf_to_md.py arquivo.pdf
python3 scripts/pdf_to_md.py arquivo.pdf -o saida.md
python3 scripts/pdf_to_md.py *.pdf                    # vários PDFs de uma vez
python3 scripts/pdf_to_md.py arquivo.pdf --forcar-ocr # ignora texto nativo, OCR em tudo
python3 scripts/pdf_to_md.py arquivo.pdf --idioma eng # OCR em inglês (padrão: por)
```

### Converter com anonimização

```bash
python3 scripts/pdf_to_md_anonimizado.py arquivo.pdf
python3 scripts/pdf_to_md_anonimizado.py arquivo.pdf --pasta-saida ./saida
```

Gera dois arquivos, sem usar o nome do PDF original (que pode identificar o
conteúdo): `projeto_AAAA-MM-DD_ref-XXXXXX.md` (texto anonimizado) e
`chave_de_desanonimizacao_AAAA-MM-DD_ref-XXXXXX.md` (correspondência
rótulo → texto original, para conferência e para reverter depois).

### Pipeline automatizado

```bash
# processa uma vez todos os arquivos pendentes nas pastas de material/
python3 scripts/auto_conversor.py

# monitora as pastas continuamente
python3 scripts/auto_conversor.py --watch

# mostra quantos arquivos estão pendentes em cada pasta
python3 scripts/auto_conversor.py --status

# mostra o progresso da conversão em andamento
python3 scripts/auto_conversor.py --progresso
```

Ou usando o atalho:

```bash
./scripts/executar_conversor.sh            # processa a fila uma vez
./scripts/executar_conversor.sh watch      # modo vigilância contínua
./scripts/executar_conversor.sh status
./scripts/executar_conversor.sh progresso
```

Fluxo de trabalho: solte o PDF (ou imagem: `.png`, `.jpg`, `.tiff`, `.bmp`)
na pasta `material/padrao/`, `material/ocr/` ou `material/anonimizacao/`
correspondente ao comportamento desejado, rode um dos comandos acima, e
pegue o `.md` gerado em `conversoes/<modo>/AAAA-MM-DD/`. Para reverter uma
anonimização, veja a seção seguinte.

## Anonimização de dados pessoais/sigilosos

Além de converter, o projeto pode anonimizar o conteúdo automaticamente
durante a mesma passagem — sem etapa manual separada e sem exigir que o
usuário informe previamente o que precisa ser ocultado.

### O que é detectado e substituído

Cada ocorrência vira um rótulo sequencial (`[cpf_1]`, `[nome_2]`,
`[tribunal_1]`...), sempre o mesmo rótulo para o mesmo dado repetido no
documento:

| Categoria | Exemplo de entrada | Exemplo de saída |
|---|---|---|
| CPF | `123.456.789-00` | `[cpf_1]` |
| CNPJ | `12.345.678/0001-00` | `[cnpj_1]` |
| Número de processo (padrão CNJ) | `0001234-56.2026.8.02.0001` | `[processo_numero_1]` |
| CEP | `57000-000` | `[cep_1]` |
| E-mail | `pessoa@exemplo.com` | `[email_1]` |
| Telefone | `(82) 99999-9999` | `[telefone_1]` |
| RG | `12.345.678-9` | `[rg_1]` |
| Endereço | `Rua das Flores, 123` | `[endereco_1]` |
| Estado / Município | `Estado Alfa`, `Município Beta` | `[estado_1]`, `[municipio_1]` |
| Tribunal/Vara/Comarca (só o nome geográfico embutido) | `Tribunal de Justiça do Estado Alfa` | `Tribunal de Justiça do Estado [estado_1]` |
| Nomes de pessoas | `João da Silva`, `Dr. Carlos Eduardo Ramos` | `[nome_1]`, `[nome_2]` |

- Dados estruturados (CPF, CNPJ, processo, CEP, e-mail, RG, telefone,
  endereço) são detectados por expressões regulares que seguem formatos
  oficiais definidos.
- Nomes de pessoas são detectados por heurística: sequências de palavras
  capitalizadas, com ou sem título de tratamento (`Dr.`, `Sr.`, `MM. Juiz(a)`,
  `Promotor(a)`, `Delegado(a)` etc.). Uma lista extensa de termos jurídicos e
  institucionais (ex.: "Ministério Público", "Poder Judiciário", "Boletim de
  Ocorrência") é usada para não confundir esses termos com nomes próprios.

### Dois arquivos de saída

Toda conversão anonimizada gera um par de arquivos, sem usar o nome do PDF
original (que já poderia identificar o conteúdo):

- `projeto_AAAA-MM-DD_ref-XXXXXX.md` — o texto convertido e anonimizado,
  com marcação de página, pronto para uso externo.
- `chave_de_desanonimizacao_AAAA-MM-DD_ref-XXXXXX.md` — a tabela de
  correspondência entre cada rótulo, o texto original substituído e as
  páginas em que ele ocorre. Deve ficar guardada em local restrito, pois
  é o que permite reverter a anonimização (veja a seção seguinte).

No pipeline automatizado (`auto_conversor.py`), a chave é nomeada de forma
espelhada ao `.md` gerado — por exemplo, `processo123.md` e
`chave_de_desanonimizacao_processo123.md` — em vez de usar o código
`ref-XXXXXX`, já que nesse modo o arquivo original é preservado (com hash
e nome) para fins de rastreabilidade, e não há necessidade de anonimizar
o próprio nome do arquivo.

No script standalone (`pdf_to_md_anonimizado.py`), o código `ref-XXXXXX`
é derivado do hash do conteúdo do PDF (não do nome do arquivo): o mesmo
documento processado de novo sempre gera o mesmo código.

### Limitações

A detecção é automática, por padrões (regex) e heurística — não há revisão
humana prévia nem lista de nomes fornecida pelo usuário. Isso tem limites
reais:

- CPF, CNPJ, número de processo, CEP, e-mail, RG e telefone seguem formatos
  bem definidos e são detectados com alta confiabilidade.
- Nomes de pessoas podem falhar: tanto deixando de anonimizar um nome fora
  do padrão esperado quanto anonimizando por engano algo que não é um nome
  (falso positivo).

**Sempre revise o arquivo `chave_de_desanonimizacao_*.md` gerado antes de
considerar o `.md` anonimizado seguro para uso externo**, especialmente em
conteúdo sigiloso. Esta ferramenta é um apoio, não um substituto do
julgamento humano sobre o que precisa ficar oculto.

## Desanonimização (revertendo o documento)

O pipeline automatizado reverte uma anonimização sozinho: basta soltar o
documento anonimizado **junto com a sua chave** na pasta
`material/desanonimizacao/` e rodar o pipeline normalmente
(`python3 scripts/auto_conversor.py` ou `./scripts/executar_conversor.sh`).

### Como o pareamento funciona

Como vários pares (documento + chave) podem ser soltos juntos na mesma
pasta de uma vez, o script precisa descobrir sozinho qual chave pertence
a qual documento. Ele tenta, nesta ordem:

1. **Nome espelhado** — se a chave se chama
   `chave_de_desanonimizacao_<nome>.md`, procura um documento chamado
   exatamente `<nome>.md` no mesmo lote (é assim que o próprio
   `auto_conversor.py` nomeia a chave no modo `anonimizacao`).
2. **Código de referência compartilhado** — se ambos os arquivos têm um
   `ref-XXXXXX` no nome, casa os que compartilham o mesmo código (é assim
   que `pdf_to_md_anonimizado.py` nomeia a saída, sem usar o nome
   original do PDF).

Se uma chave for solta sem o documento correspondente (ou vice-versa), o
script simplesmente aguarda — nada é processado até que o par completo
esteja presente, e um aviso é impresso indicando o que falta.

### Saída gerada

Para cada par reconhecido, o script cria uma pasta em
`conversoes/desanonimizacao/AAAA-MM-DD/<nome-do-documento>/` contendo os
três arquivos juntos:

```
conversoes/desanonimizacao/2026-09-13/processo123/
├── processo123.md                              # documento anonimizado (movido da entrada)
├── chave_de_desanonimizacao_processo123.md     # chave usada (movida da entrada)
└── desanonimizado_processo123.md               # texto já revertido/preenchido
```

## Licença

Distribuído sob a licença MIT — veja [LICENSE](LICENSE).
