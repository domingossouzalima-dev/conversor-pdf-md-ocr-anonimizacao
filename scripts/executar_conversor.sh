#!/usr/bin/env bash
# ==============================================================================
# executar_conversor.sh — Execução e Monitoramento do Pipeline de Conversões
# Copyright (c) 2026 domingossouzalima-dev — Licença MIT
# ==============================================================================

DIR_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$(command -v python3 || command -v python)"

if [ -z "$PYTHON_BIN" ]; then
    echo "Erro: python3 não encontrado no PATH." >&2
    exit 1
fi

case "${1:-processar}" in
    watch|vigiar|-w|--watch)
        echo "Iniciando conversor no modo vigilância contínua..."
        "$PYTHON_BIN" "$DIR_SCRIPT/auto_conversor.py" --watch
        ;;
    progresso|-p|--progresso)
        "$PYTHON_BIN" "$DIR_SCRIPT/auto_conversor.py" --progresso
        ;;
    status|-s|--status)
        "$PYTHON_BIN" "$DIR_SCRIPT/auto_conversor.py" --status
        ;;
    *)
        echo "Varrendo e processando arquivos pendentes nas pastas de entrada..."
        "$PYTHON_BIN" "$DIR_SCRIPT/auto_conversor.py"
        ;;
esac
