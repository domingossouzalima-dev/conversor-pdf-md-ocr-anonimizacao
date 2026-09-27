#!/usr/bin/env python3
"""
distribuir_materias_trf2.py
Classifica e distribui os arquivos Markdown convertidos para as pastas
temáticas do TRF2 dentro de 01-concursos-juridicos/magistratura/trf_2/.
Custo em tokens: 0 (classificação léxica determinística local de alta precisão).
"""

import os
import re
import glob
import shutil
from collections import defaultdict

# Diretórios
BASE_DIR = "/home/domingos/Gemini"
SRC_DIR = os.path.join(BASE_DIR, "12-conversoes-pdf-md/arquivos-de-saida/padrao/2026-09-16")
LOG_PATH = os.path.join(BASE_DIR, "12-conversoes-pdf-md/log/2026-09-16/conversoes_2026-09-16.log")
DEST_BASE = os.path.join(BASE_DIR, "01-concursos-juridicos/magistratura/trf_2")

# Mapeamento de pastas
PASTAS = {
    "01_direito_constitucional": "01_direito_constitucional",
    "02_direito_administrativo": "02_direito_administrativo",
    "03_direito_civil": "03_direito_civil",
    "04_direito_processual_civil": "04_direito_processual_civil",
    "05_direito_penal": "05_direito_penal",
    "06_direito_processual_penal": "06_direito_processual_penal",
    "07_direito_previdenciario": "07_direito_previdenciario",
    "08_direito_financeiro": "08_direito_financeiro",
    "09_direito_tributario": "09_direito_tributario",
    "10_direito_ambiental": "10_direito_ambiental",
    "11_direito_internacional": "11_direito_internacional",
    "12_direito_economico_e_consumidor": "12_direito_economico_e_consumidor",
    "13_direito_empresarial": "13_direito_empresarial",
    "14_formacao_humanistica": "14_formacao_humanistica",
    "15_direitos_humanos": "15_direitos_humanos",
    "16_diversos": "16_diversos"
}

def carregar_mapa_paginas_log():
    pages_map = {}
    if not os.path.exists(LOG_PATH):
        return pages_map
    with open(LOG_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        log_text = f.read()
    entries = log_text.split('------------------------------------------------------------------------------')
    for e in entries:
        m_md = re.search(r'Markdown Gerado\s*:\s*(.+)', e)
        m_pg = re.search(r'Total de Páginas\s*:\s*(\d+)', e)
        if m_md and m_pg:
            base = os.path.basename(m_md.group(1).strip())
            pages_map[base] = int(m_pg.group(1))
    return pages_map

def classificar_arquivo(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as fp:
        content = fp.read(4500)
    
    # 1. Extração do bloco da Página 1
    p1 = re.search(r'## Página 1\s*\n(.*?)(?=\n---|\n## Página 2|\Z)', content, re.DOTALL)
    text_block = ""
    if p1:
        lines = [l.strip() for l in p1.group(1).split('\n') if l.strip()]
        cleaned = [l for l in lines if l not in [
            'PDF SINTÉTICO', 'SISTEMA DE ENSINO', 'GRAN CURSOS ONLINE', 
            'GRAN', 'LIVRO ELETRÔNICO', 'LIVRO ELETRONICO'
        ]]
        text_block = " ".join(cleaned[:4]).upper()
    
    fn = os.path.basename(file_path).upper()
    full_search = f"{text_block} {fn}"
    
    # Regras refinadas de classificação
    
    # Previdenciário
    if any(k in full_search for k in ['PREVIDENCIÁRIO', 'PREVIDENCIARIO', 'SEGURIDADE SOCIAL', 'RGPS', 'RPPS', 'BENEFÍCIOS PREVIDENCIÁRIOS', 'BENEFICIOS PREVIDENCIARIOS']):
        return "07_direito_previdenciario"
        
    # Financeiro
    if any(k in full_search for k in ['FINANCEIRO', 'ORÇAMENTÁRIO', 'ORCAMENTARIO', 'RESPONSABILIDADE FISCAL', 'LRF', 'CRÉDITO PÚBLICO', 'CREDITO PUBLICO', 'DÍVIDA PÚBLICA', 'DIVIDA PUBLICA', 'PRECATÓRIOS', 'PRECATORIOS']):
        return "08_direito_financeiro"
        
    # Tributário
    if any(k in full_search for k in ['TRIBUTÁRIO', 'TRIBUTARIO', 'CÓDIGO TRIBUTÁRIO', 'SISTEMA TRIBUTÁRIO', 'IMPOSTOS', 'TAXAS', 'CONTRIBUIÇÕES DE MELHORIA', 'EXECUÇÃO FISCAL']):
        return "09_direito_tributario"
        
    # Ambiental
    if any(k in full_search for k in ['AMBIENTAL', 'MEIO AMBIENTE', 'SNUC', 'UNIDADES DE CONSERVAÇÃO', 'UNIDADES DE CONSERVACAO', 'FLORESTAL', 'PNRS', 'RECURSOS HÍDRICOS', 'CONAMA', 'SISNAMA']):
        return "10_direito_ambiental"
        
    # Direitos Humanos & Antidiscriminação
    if any(k in full_search for k in ['DIREITOS HUMANOS', 'ANTIDISCRIMINAÇÃO', 'ANTIDISCRIMINACAO', 'DISCRIMINAÇÃO RACIAL', 'DISCRIMINACAO RACIAL', 'PESSOAS COM DEFICIÊNCIA', 'PESSOAS COM DEFICIENCIA', 'QUILOMBOLAS', 'INDÍGENAS', 'INDIGENAS', 'LGBTQIA', 'INTOLERÂNCIA RELIGIOSA', 'INTOLERANCIA RELIGIOSA']):
        return "15_direitos_humanos"
        
    # Formação Humanística
    if any(k in full_search for k in ['FORMAÇÃO HUMANÍSTICA', 'FORMACAO HUMANISTICA', 'FILOSOFIA DO DIREITO', 'SOCIOLOGIA DO DIREITO', 'TEORIA GERAL DO DIREITO', 'PSICOLOGIA JUDICIÁRIA', 'ÉTICA DA MAGISTRATURA', 'ETICA DA MAGISTRATURA', 'DEONTOLOGIA']):
        return "14_formacao_humanistica"
        
    # Internacional
    if any(k in full_search for k in ['INTERNACIONAL PÚBLICO', 'INTERNACIONAL PRIVADO', 'INTERNACIONAL', 'TRATADOS INTERNACIONAIS', 'CORTE INTERAMERICANA', 'EXTRADIÇÃO', 'EXTRADICAO']):
        return "11_direito_internacional"
        
    # Econômico e Consumidor
    if any(k in full_search for k in ['CONSUMIDOR', 'CDC', 'ECONÔMICO', 'ECONOMICO', 'CADE', 'CONCORRÊNCIA', 'DEFESA DO CONSUMIDOR', 'RELAÇÕES DE CONSUMO']):
        return "12_direito_economico_e_consumidor"
        
    # Empresarial
    if any(k in full_search for k in ['EMPRESARIAL', 'COMERCIAL', 'FALÊNCIA', 'FALENCIA', 'RECUPERAÇÃO JUDICIAL', 'SOCIEDADE ANÔNIMA', 'SOCIEDADE LIMITADA', 'TÍTULOS DE CRÉDITO', 'TITULOS DE CREDITO', 'PROPRIEDADE INDUSTRIAL']):
        return "13_direito_empresarial"
        
    # Processual Penal (antes de penal genérico)
    if any(k in full_search for k in ['PROCESSUAL PENAL', 'PROCESSO PENAL', 'CPP', 'INQUÉRITO POLICIAL', 'INQUERITO POLICIAL', 'AÇÃO PENAL', 'ACAO PENAL', 'JURISDIÇÃO PENAL', 'COMPETÊNCIA PENAL', 'PROVAS NO PROCESSO PENAL', 'PRISÃO CAUTELAR', 'PRISAO CAUTELAR', 'LIBERDADE PROVISÓRIA', 'JÚRI', 'JURI', 'HABEAS CORPUS', 'RECURSOS PENAIS', 'EXECUÇÃO PENAL', 'EXECUCAO PENAL', 'NULIDADES PROCESSUAIS PENAIS']):
        return "06_direito_processual_penal"
        
    # Processual Civil (antes de civil genérico)
    if any(k in full_search for k in ['PROCESSUAL CIVIL', 'PROCESSO CIVIL', 'CPC', 'PETIÇÃO INICIAL', 'CONTESTAÇÃO', 'RECURSOS CÍVEIS', 'CUMPRIMENTO DE SENTENÇA', 'EXECUÇÃO DE TÍTULO', 'PROCEDIMENTOS ESPECIAIS', 'TUTELA PROVISÓRIA', 'JURISDIÇÃO CONTENCIOSA']):
        return "04_direito_processual_civil"
        
    # Penal (Material)
    if any(k in full_search for k in ['DIREITO PENAL', 'CÓDIGO PENAL', 'TEORIA DO CRIME', 'CULPABILIDADE', 'TIPICIDADE', 'DOSIMETRIA DA PENA', 'CRIMES CONTRA', 'LEI DE DROGAS', 'CRIMES HEDIONDOS', 'LEI N. 8.069/1990 - CRIMES', 'LEGISLAÇÃO PENAL', 'LEGISLACAO PENAL']):
        return "05_direito_penal"
        
    # Constitucional
    if any(k in full_search for k in ['CONSTITUCIONAL', 'CONTROLE DE CONSTITUCIONALIDADE', 'DIREITOS FUNDAMENTAIS', 'PODER JUDICIÁRIO', 'PODER EXECUTIVO', 'PODER LEGISLATIVO', 'AÇÕES CONSTITUCIONAIS', 'FUNÇÕES ESSENCIAIS À JUSTIÇA', 'REPARTIÇÃO DE COMPETÊNCIAS NA CF', 'SERVIDORES PÚBLICOS NA CF']):
        return "01_direito_constitucional"
        
    # Administrativo
    if any(k in full_search for k in ['ADMINISTRATIVO', 'LICITAÇÃO', 'LICITACAO', '14.133', '8.666', 'IMPROBIDADE', '8.429', 'RESPONSABILIDADE CIVIL DO ESTADO', 'ATOS ADMINISTRATIVOS', 'PODERES ADMINISTRATIVOS', 'SERVIÇOS PÚBLICOS', 'DESAPROPRIAÇÃO']):
        return "02_direito_administrativo"
        
    # Civil
    if any(k in full_search for k in ['DIREITO CIVIL', 'CÓDIGO CIVIL', 'LINDB', 'PARTE GERAL DO DIREITO CIVIL', 'OBRIGAÇÕES', 'OBRIGACOES', 'CONTRATOS', 'RESPONSABILIDADE CIVIL', 'DIREITO DAS COISAS', 'DIREITO DE FAMÍLIA', 'SUCESSÕES', 'SUCESSOES', 'POSSE E PROPRIEDADE']):
        return "03_direito_civil"
        
    # Fallback no nome do arquivo puro
    if 'PENAL' in fn or 'CRIME' in fn: return "05_direito_penal"
    if 'CIVIL' in fn: return "03_direito_civil"
    if 'ADMIN' in fn: return "02_direito_administrativo"
    if 'CONST' in fn: return "01_direito_constitucional"
    
    return "16_diversos"

def main():
    print("Iniciando criação de pastas e distribuição...")
    
    # 1. Criar pastas destino
    for pasta in PASTAS.values():
        dir_path = os.path.join(DEST_BASE, pasta)
        os.makedirs(dir_path, exist_ok=True)
    
    # 2. Carregar log
    pages_map = carregar_mapa_paginas_log()
    
    # 3. Listar arquivos MD
    md_files = sorted(glob.glob(os.path.join(SRC_DIR, "*.md")))
    print(f"Total de arquivos MD encontrados para distribuir: {len(md_files)}")
    
    distribuicao = defaultdict(list)
    
    for f in md_files:
        base_name = os.path.basename(f)
        cat = classificar_arquivo(f)
        dest_file = os.path.join(DEST_BASE, cat, base_name)
        
        # Copiar arquivo preservando atributos
        shutil.copy2(f, dest_file)
        
        paginas = pages_map.get(base_name, 0)
        tamanho_kb = os.path.getsize(f) / 1024.0
        distribuicao[cat].append({
            "nome": base_name,
            "paginas": paginas,
            "tamanho_kb": tamanho_kb
        })

    # 4. Gerar Relatório Consolidado em Markdown
    relatorio_path = os.path.join(DEST_BASE, "relatorio_distribuicao.md")
    with open(relatorio_path, 'w', encoding='utf-8') as rep:
        rep.write("# Relatório de Distribuição de Arquivos — TRF2\n\n")
        rep.write(f"**Data da Distribuição:** 2026-09-16\n")
        rep.write(f"**Origem:** `{SRC_DIR}`\n")
        rep.write(f"**Destino:** `{DEST_BASE}`\n\n")
        rep.write("| Código | Matéria / Pasta | Arquivos | Páginas (Log) | Tamanho (MB) |\n")
        rep.write("| :--- | :--- | :---: | :---: | :---: |\n")
        
        total_arq = 0
        total_pag = 0
        total_kb = 0
        
        for pasta in sorted(PASTAS.values()):
            items = distribuicao[pasta]
            q_arq = len(items)
            q_pag = sum(x["paginas"] for x in items)
            q_kb = sum(x["tamanho_kb"] for x in items)
            
            total_arq += q_arq
            total_pag += q_pag
            total_kb += q_kb
            
            nome_amigavel = pasta[3:].replace('_', ' ').title()
            rep.write(f"| `{pasta[:2]}` | {nome_amigavel} | {q_arq} | {q_pag:,} | {q_kb/1024:.2f} MB |\n")
            
        rep.write(f"| **TOTAL** | **Consolidado Geral** | **{total_arq}** | **{total_pag:,}** | **{total_kb/1024:.2f} MB** |\n\n")
        
        rep.write("---\n\n## Detalhamento dos Arquivos por Pasta\n\n")
        for pasta in sorted(PASTAS.values()):
            items = distribuicao[pasta]
            nome_amigavel = pasta[3:].replace('_', ' ').title()
            rep.write(f"### {pasta} ({nome_amigavel}) — {len(items)} arquivos\n\n")
            if not items:
                rep.write("*Nenhum arquivo nesta pasta.*\n\n")
                continue
            for item in sorted(items, key=lambda x: x["paginas"]):
                rep.write(f"- `{item['nome']}` — **{item['paginas']} págs** ({item['tamanho_kb']:.1f} KB)\n")
            rep.write("\n")

    print("Distribuição finalizada com sucesso!")
    print(f"Relatório gerado em: {relatorio_path}")

if __name__ == "__main__":
    main()
