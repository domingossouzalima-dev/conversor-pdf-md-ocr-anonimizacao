# Conversor de PDF para Markdown COM ANONIMIZAÇÃO

Script: `pdf_to_md_anonimizado.py`

Este é o mesmo conversor de PDF para Markdown (com marcação `## Página N`),
mas com uma etapa a mais: antes de gravar o `.md`, ele **anonimiza
automaticamente** dados pessoais e informações que permitiriam identificar
o processo, em linha com o espírito da **Resolução CNJ nº 615/2025**
(art. 7º, §2º; art. 19, §3º, IV; e art. 30 e §1º), que exige que dados
sigilosos e pessoais sejam anonimizados/pseudonimizados **na origem**
antes de serem submetidos a ferramentas de inteligência artificial
externas.

## O que é anonimizado automaticamente

- Nome do estado (`estado_1`...) e do município/capital (`municipio_1`...)
  — inclusive quando aparecem DENTRO do nome de um órgão. Por exemplo,
  "Governo do Estado de Alagoas" vira "Governo do Estado [estado_1]", e
  "Polícia Civil do Estado de Alagoas" vira "Polícia Civil do Estado
  [estado_1]": o órgão continua identificável (útil para pesquisa
  jurídica), só o nome do estado/cidade fica oculto.
- Tipo de tribunal, vara, comarca ou fórum (`tribunal_1`, `tribunal_2`...)
  — pelo mesmo motivo, só o "tipo" do órgão (TJ, STJ, Vara Criminal,
  Comarca...) vira rótulo; o nome do estado/cidade dentro dele já foi
  tratado pela categoria acima.
- Número de processo, no padrão CNJ (`processo_numero_1`...)
- CPF (`cpf_1`...) e CNPJ (`cnpj_1`...)
- RG (`rg_1`...)
- Telefones (`telefone_1`...)
- E-mails (`email_1`...)
- Endereços — Rua/Av./Alameda etc. com número (`endereco_1`...)
- CEP (`cep_1`...)
- Nomes de pessoas — partes, vítimas, testemunhas, juízes, promotores,
  defensores, delegados, advogados, servidores (`nome_1`, `nome_2`...),
  reconhecidos tanto em Capitalização Normal quanto TODO EM CAIXA ALTA
  (comum em boletins de ocorrência e blocos de assinatura digital)

Cada tipo de dado recebe um rótulo sequencial próprio, na ordem em que
aparece no documento — e a MESMA entidade (ex.: "Alagoas" e "ALAGOAS", ou
"Tribunal de Justiça" e "TRIBUNAL DE JUSTIÇA") sempre recebe o mesmo
rótulo, mesmo que apareça grafada de formas diferentes ao longo do
documento. O nome do arquivo PDF de origem também não é usado para
nomear a saída (veja mais abaixo), já que ele mesmo poderia identificar
o processo.

**Nota sobre "Pará":** por coincidir com a preposição comum "para", o
nome do estado do Pará só é anonimizado quando aparece com um contexto
claramente geográfico ao lado (ex.: "Estado do Pará", "Belém/PA"). Fora
desse contexto, a palavra "para" é sempre deixada como está — isso evita
corromper frases comuns, ao custo de eventualmente não anonimizar "Pará"
em alguma frase muito atípica. Todos os outros 26 estados não têm esse
problema e são detectados normalmente.

## Como os nomes de pessoas são detectados (e por que isso importa)

Diferente de CPF, telefone ou número de processo — que seguem um formato
fixo e são detectados com alta confiabilidade — **nomes de pessoas não
têm um padrão fixo**. O script usa uma heurística totalmente automática:

- sequências de palavras capitalizadas (ex.: "João da Silva Pereira"),
  reconhecidas tanto em Capitalização Normal quanto TODO EM CAIXA ALTA
  (comum em boletins de ocorrência e blocos de assinatura digital);
- nomes precedidos de título/cargo (ex.: "Dr.", "MM. Juiz", "Delegado",
  "Promotora", "Defensor Público" — o título é descartado e só a pessoa
  vira rótulo);
- uma lista extensa de palavras institucionais, jurídicas e de
  formulário (ex.: "Ministério Público", "Código Penal", "Data de
  Nascimento", "Local do Fato", "Instituto Médico Legal") é usada para
  evitar que essas expressões sejam confundidas com nomes de pessoas —
  essencial em boletins de ocorrência e autos policiais, que têm muitos
  campos e cabeçalhos de formulário em maiúsculas;
- um limite de tamanho: um bloco de palavras capitalizadas com mais de
  6 palavras não é tratado como nome (nomes reais raramente passam
  disso; blocos maiores costumam ser frases inteiras de relato que
  escaparam da lista de stopwords, como um trecho de depoimento todo em
  caixa alta).

**Isso funciona bem na maioria dos casos, mas não é infalível.** Pode
haver, ocasionalmente:

- um nome fora do padrão esperado que passe sem ser anonimizado (falso
  negativo);
- uma expressão que não é nome de pessoa e seja anonimizada por engano
  (falso positivo) — nesse caso, ela só vira um rótulo a mais e não
  compromete o sigilo de ninguém, apenas deixa o texto um pouco mais
  "rotulado" do que o necessário.

**Por isso, sempre revise o arquivo de mapa (explicado abaixo) antes de
considerar o `.md` anonimizado seguro para envio a qualquer ferramenta
externa, especialmente em processos sob segredo de justiça.** Este script
é uma ferramenta de apoio à anonimização, não um substituto do julgamento
humano sobre o que é sigiloso naquele processo específico.

## Nomenclatura dos arquivos gerados (anonimizada também no nome)

Para não correr o risco de o próprio **nome do arquivo** revelar o
processo (por exemplo, se o PDF já se chamar
`processo_joao_silva_furto.pdf`), a saída usa um nome de arquivo
genérico, baseado em data e em um código de referência curto:

```
projeto_2026-09-07_ref-a1b2c3.md    <- texto anonimizado
mapa_2026-09-07_ref-a1b2c3.md       <- mapa de anonimização (mesma referência)
```

- A data é a do dia em que a conversão foi feita.
- O código (`a1b2c3`) é calculado a partir do conteúdo do PDF (não do
  nome do arquivo nem de nenhum dado pessoal extraído) — o mesmo PDF
  gera sempre o mesmo código, o que ajuda a saber se aquele documento já
  havia sido convertido antes, sem expor qualquer informação sobre ele.
- O arquivo de mapa sempre leva o prefixo `mapa_` seguido da mesma
  referência do `.md` anonimizado correspondente, para deixar clara a
  correspondência entre os dois.

Por padrão, os dois arquivos são salvos na mesma pasta do PDF de entrada.
Para escolher outra pasta:

```bash
python3 pdf_to_md_anonimizado.py meu_arquivo.pdf --pasta-saida ./anonimizados
```

## O arquivo de MAPA — trate como documento sigiloso

O `mapa_AAAA-MM-DD_ref-XXXXXX.md` é o que permite reverter a anonimização:
ele lista, para cada rótulo usado (ex.: `nome_3`, `cpf_1`), o texto
original exato que foi substituído e a(s) página(s) em que ele aparece no
PDF — um item embaixo do outro (não em tabela), para ficar legível mesmo
quando o texto original é longo. Exemplo de como fica:

```
## Nomes de Pessoas

nome_1 → Carlos Eduardo Ramos
Páginas: 1

nome_2 → Antonio Marques dos Santos
Páginas: 1
```

**Esse arquivo tem, reunidos em um só lugar, todos os dados sensíveis do
processo — trate-o com o mesmo cuidado (ou mais) que o PDF original.**
Ele é o que você guarda para si (ou entrega apenas a quem tiver acesso
autorizado ao processo); é o `.md` SEM o "mapa_" na frente que você pode
levar para pesquisa em ferramentas de IA.

## Como usar

Mesma instalação do conversor original (`pdf_to_md.py`) — se você já
seguiu o `LEIA-ME.md` (Linux) ou `LEIA-ME-WINDOWS.md` (Windows), nenhuma
dependência nova é necessária.

```bash
# Converter e anonimizar um PDF
python3 pdf_to_md_anonimizado.py meu_processo.pdf

# Vários PDFs de uma vez
python3 pdf_to_md_anonimizado.py *.pdf

# Escolher pasta de saída
python3 pdf_to_md_anonimizado.py meu_processo.pdf --pasta-saida ./anonimizados

# Forçar OCR em todas as páginas (útil se o PDF for todo escaneado)
python3 pdf_to_md_anonimizado.py meu_processo.pdf --forcar-ocr
```

## Rotina sugerida

1. Salve o PDF do processo na pasta de trabalho.
2. Rode `python3 pdf_to_md_anonimizado.py nome_do_arquivo.pdf`.
3. Abra o arquivo de mapa (`mapa_...`) e confira rapidamente se algum
   dado sensível ficou de fora, ou se algo foi anonimizado sem
   necessidade.
4. Só então anexe aqui na conversa o arquivo `projeto_...md` (o texto
   anonimizado) — nunca o arquivo `mapa_...md`.
