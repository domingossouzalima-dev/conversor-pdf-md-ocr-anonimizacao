# Conversor de PDF para Markdown no Windows

Duas rotas, dependendo da sua situação:

- **Opção A** — você PODE instalar programas (Python) no seu Windows.
- **Opção B** — você NÃO tem autorização para instalar nada (máquina corporativa travada).

---

## OPÇÃO A — Com Python (recomendada se puder instalar)

### A.1. Instalar o Python

1. Baixe em: https://www.python.org/downloads/windows/ (botão amarelo "Download Python 3.x.x").
2. Ao abrir o instalador, **marque a caixinha "Add Python to PATH"** na primeira tela — isso é essencial, senão os comandos abaixo não funcionam.
3. Clique em "Install Now" e aguarde.
4. Abra o **Prompt de Comando** (tecla Windows → digite `cmd` → Enter) e confirme:

```cmd
python --version
```

Se aparecer algo como `Python 3.12.x`, está instalado corretamente.

### A.2. Instalar o Tesseract OCR (para páginas escaneadas) e o Poppler

**Tesseract:**
1. Baixe o instalador em: https://github.com/UB-Mannheim/tesseract/wiki (link "tesseract-ocr-w64-setup-...exe").
2. Instale normalmente. Durante a instalação, na tela de "Additional language data", marque **Portuguese** para ter OCR em português.
3. Anote o caminho de instalação (geralmente `C:\Program Files\Tesseract-OCR`).

**Poppler** (necessário para o script renderizar páginas escaneadas como imagem):
1. Baixe em: https://github.com/oschwartz10612/poppler-windows/releases (arquivo `.zip` mais recente).
2. Extraia o `.zip`, por exemplo, para `C:\poppler`.
3. Você vai precisar do caminho da subpasta `Library\bin` dentro dele (ex.: `C:\poppler\Library\bin`).

### A.3. Adicionar Tesseract e Poppler ao PATH do Windows

1. Tecla Windows → digite "variáveis de ambiente" → abra "Editar as variáveis de ambiente do sistema".
2. Clique em "Variáveis de Ambiente...".
3. Em "Variáveis do sistema", selecione `Path` → "Editar" → "Novo".
4. Adicione as duas linhas (ajuste conforme onde você instalou):
   - `C:\Program Files\Tesseract-OCR`
   - `C:\poppler\Library\bin`
5. Clique OK em tudo e **feche e abra um novo Prompt de Comando** (isso é necessário para o PATH atualizar).
6. Teste:

```cmd
tesseract --version
pdftoppm -v
```

Se as duas mostrarem uma versão, está tudo certo.

### A.4. Instalar as bibliotecas Python

```cmd
pip install pypdf pdf2image pytesseract pillow
```

(no Windows normalmente não dá o erro "externally-managed-environment" que apareceu no Linux; se der, use `pip install --user pypdf pdf2image pytesseract pillow`)

### A.5. Usar o script

Coloque o arquivo `pdf_to_md.py` (o mesmo script, já enviado) na mesma pasta do PDF, abra o Prompt de Comando nessa pasta (dica: na pasta pelo Explorador de Arquivos, clique na barra de endereço, digite `cmd` e Enter) e rode:

```cmd
python pdf_to_md.py meu_arquivo.pdf
```

Isso gera `meu_arquivo.md` na mesma pasta. Para escolher outro nome/local de saída:

```cmd
python pdf_to_md.py meu_arquivo.pdf -o resultado.md
```

---

## OPÇÃO B — Sem poder instalar nada

Se você não tem permissão para instalar programas, a saída prática é usar
uma ferramenta que **já vem pronta no Windows/Office corporativo** para
extrair o texto do PDF (inclusive com OCR embutido em páginas escaneadas),
e depois um passo simples de formatação com marcação de página.

### B.1. Extrair o texto do PDF com o Word (tem OCR embutido)

O Microsoft Word abre PDFs e faz OCR automaticamente em páginas escaneadas
— e isso normalmente já vem instalado, sem precisar de permissão extra.

1. Abra o **Word**.
2. Arquivo → Abrir → selecione o PDF.
3. O Word vai avisar algo como "O Word vai converter este PDF em um documento editável..." → clique em **OK**.
   - Aqui está o pulo do gato: se o PDF tiver páginas escaneadas, o Word
     já roda OCR nelas sozinho durante essa conversão.
4. Aguarde a conversão (pode demorar em PDFs grandes).
5. **Importante para não perder a marcação de página**: antes de mais nada,
   com o documento já convertido, vá inserindo manualmente uma marca de
   página nos pontos em que uma página do PDF original termina e a outra
   começa. Sugestão: coloque o cursor no início de cada nova página do
   PDF original e digite uma linha assim:

   ```
   ===PAGINA 12===
   ```

   (Dica: como o Word mantém a paginação visualmente parecida com a do PDF
   original na maioria dos casos, dá para usar isso como guia — mas
   sempre confira comparando com o PDF aberto ao lado, porque a
   conversão pode reorganizar quebras de página.)

6. Arquivo → Salvar Como → escolha o tipo **"Texto sem Formatação (*.txt)"**
   → salve com um nome, ex.: `meu_arquivo_bruto.txt`.

### B.2. Transformar o .txt marcado em .md com marcação de página correta

Cole o conteúdo do `.txt` (com as marcas `===PAGINA N===` que você inseriu)
diretamente aqui na nossa conversa, ou anexe o `.txt`, e eu mesmo converto
para o `.md` final no formato `## Página N` — sem precisar rodar nada no
seu computador.

Se preferir fazer isso você mesmo, também dá para usar o **Bloco de Notas**
com localizar-e-substituir (Ctrl+H):
- Localizar: `===PAGINA `
- Substituir por: `## Página `
- Também substitua `===` (o fechamento) por nada (deixe em branco), já
  que ele não é necessário no Markdown.

### B.3. Alternativa dentro da Opção B: sites de OCR/conversão online

Se preferir não usar o Word, existem serviços online gratuitos que fazem
"PDF para texto" com OCR (você faz upload do PDF, ele devolve o texto).
Como isso envolve enviar o conteúdo do PDF para um servidor de terceiros,
**não recomendo para documentos sigilosos ou processos sob segredo de
justiça** — nesse caso, prefira sempre a rota do Word (roda local, no seu
próprio computador) ou a Opção A com Python.

Se o documento não for sensível e você quiser essa rota, me avise que eu
te oriento sobre como estruturar o texto resultante no formato de página
esperado.

---

## Qual opção escolher?

- Se você conseguir pedir liberação de instalação ao TI, ou já tem
  autonomia no seu Windows: **Opção A** é mais precisa e automática,
  principalmente para lotes grandes de PDFs.
- Se está travado por política corporativa: **Opção B com Word** é a mais
  confiável, porque usa um programa que você certamente já tem, roda
  localmente (sem expor documentos sigilosos a terceiros) e já resolve o
  OCR sozinho.
