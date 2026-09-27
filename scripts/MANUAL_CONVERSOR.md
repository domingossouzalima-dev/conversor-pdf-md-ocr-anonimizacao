# Manual do Sistema Automatizado de Conversão (conversao-pdf)

Este diretório abriga os scripts de processamento e conversão de documentos (PDFs e Imagens) para Markdown, com preservação de paginação, aplicação de OCR e anonimização de dados conforme a **Resolução CNJ nº 615/2025**. Compartilhado entre Antigravity e Claude Code.

---

## 1. Fluxo de Trabalho e Pastas de Entrada/Saída

Basta depositar o arquivo na pasta correspondente ao modo desejado dentro de `arquivos-de-entrada/`:

| Pasta de Entrada (`arquivos-de-entrada/`) | Modo de Processamento | Destino do Markdown (`arquivos-de-saida/`) | Destino do PDF/Original (`arquivos-de-saida/pdf/`) |
| :--- | :--- | :--- | :--- |
| `arquivos-de-entrada/padrao/` | **Padrão:** Extrai texto nativo em alta velocidade via PyMuPDF. Se a página for escaneada/imagem (< 25 caracteres), aplica OCR Tesseract automaticamente apenas nessa página. | `arquivos-de-saida/padrao/AAAA-MM-DD/` | `arquivos-de-saida/pdf/AAAA-MM-DD/` |
| `arquivos-de-entrada/ocr/` | **OCR Otimizado (Estratégia 2):** Processa com **OCRmyPDF** aplicando correção angular de inclinação (`--deskew`), auto-rotação de laudas deitadas/invertidas (`--rotate-pages`), remoção de ruídos de digitalização (`--clean`) e OCR forçado em português. Caso o OCRmyPDF não esteja disponível no ambiente, aciona automaticamente o fallback via PyMuPDF + Tesseract 300 DPI. | `arquivos-de-saida/ocr/AAAA-MM-DD/` | `arquivos-de-saida/pdf/AAAA-MM-DD/` |
| `arquivos-de-entrada/anonimizacao/` | **Anonimização:** Oculta dados pessoais e processuais sensíveis (CPF, CNPJ, autos CNJ, endereços, partes) gerando o texto anonimizado e o `_MAPA.md` de conferência (Res. CNJ nº 615/2025). | `arquivos-de-saida/anonimizacao/AAAA-MM-DD/` | `arquivos-de-saida/pdf/AAAA-MM-DD/` |

---

## 2. Ações Executadas Automaticamente

Ao processar cada arquivo:
1. **Criação da Pasta do Dia:** Cria automaticamente a subpasta `AAAA-MM-DD` dentro de `arquivos-de-saida/<modo>/` e em `arquivos-de-saida/pdf/`.
2. **Geração do Markdown com Rastreabilidade e Numeração de Laudas:**
   - Cada página do documento recebe a marcação: `## Página N` (ou `## Página N (OCR Otimizado - OCRmyPDF)`).
   - O arquivo `.md` contém cabeçalho detalhado com o nome do arquivo original, modalidade, motor utilizado, data e hora exata, total de páginas, páginas processadas com OCR e hash SHA-256 para integridade e conferência forense.
3. **Transporte Seguro do Arquivo Original para a Pasta PDF:**
   - O arquivo PDF/imagem de entrada é movido da pasta `arquivos-de-entrada/<modo>/` para a pasta dedicada do dia em `arquivos-de-saida/pdf/AAAA-MM-DD/`, mantendo a pasta de entrada limpa e separando os PDFs convertidos dos arquivos Markdown.
4. **Log Diário Automatizado:**
   - Gravação de relatório estruturado de todas as conversões (sucesso ou eventuais falhas) na subpasta `log/AAAA-MM-DD/conversoes_AAAA-MM-DD.log`.

---

## 3. Formas de Execução e Acompanhamento

No terminal Linux:

### A. Acompanhamento de Progresso em Tempo Real:
Para checar a conversão ativa em andamento (página atual, porcentagem, tempo decorrido e tempo restante estimado):
```bash
/home/domingos/base-compartilhada/conversao-pdf/scripts/executar_conversor.sh progresso
```

### B. Execução Sob Demanda (Processar Fila):
Varre as pastas de entrada uma vez, converte o que estiver pendente e finaliza:
```bash
/home/domingos/base-compartilhada/conversao-pdf/scripts/executar_conversor.sh
```

### C. Modo Vigilância Contínua (Watch):
Fica monitorando em tempo real as 3 pastas de entrada. Assim que você colar ou salvar um arquivo lá, a conversão ocorre em segundos:
```bash
/home/domingos/base-compartilhada/conversao-pdf/scripts/executar_conversor.sh vigiar
```
*(Nota: No Linux, o serviço de usuário `conversor.service` via systemd já roda essa vigilância em segundo plano de forma contínua).*

### D. Verificação de Status das Pastas:
```bash
/home/domingos/base-compartilhada/conversao-pdf/scripts/executar_conversor.sh status
```

---

## 4. Configuração no Windows

Para executar a **Estratégia 2 (OCRmyPDF)** no Windows:
1. Instale o Python 3.10+ (marcando "Add python.exe to PATH").
2. Instale as bibliotecas Python:
   ```cmd
   pip install pymupdf pytesseract pillow pypdf pdf2image ocrmypdf
   ```
3. Instale o **Tesseract OCR** e o **Ghostscript** (necessário para OCRmyPDF):
   ```cmd
   winget install UB-Mannheim.TesseractOCR
   winget install ArtifexSoftware.Ghostscript
   ```
4. Baixe o modelo treinado em português (`por.traineddata`) para a pasta `tessdata` do Tesseract.
5. Se não desejar instalar o Ghostscript ou OCRmyPDF no Windows, não se preocupe: o script ativa **automaticamente o fallback** de PyMuPDF + Tesseract 300 DPI, convertendo normalmente sem interrupções.
