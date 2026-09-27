@echo off
chcp 65001 > nul
title Conversor Gemini - Processamento Manual de Arquivos

echo ==============================================================================
echo  Conversor Gemini: Processamento de PDF / Imagens para Markdown
echo ==============================================================================
echo.
echo Processando arquivos pendentes nas pastas:
echo   - 12-conversoes-pdf-md\arquivos-de-entrada\padrao\
echo   - 12-conversoes-pdf-md\arquivos-de-entrada\ocr\
echo   - 12-conversoes-pdf-md\arquivos-de-entrada\anonimizacao\
echo.

python "%~dp0auto_conversor.py"

echo.
echo ==============================================================================
echo  Processamento concluido. Verifique os resultados em 12-conversoes-pdf-md\arquivos-de-saida\
echo ==============================================================================
pause
