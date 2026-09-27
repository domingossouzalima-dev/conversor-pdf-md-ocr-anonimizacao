@echo off
chcp 65001 > nul
title Conversor Gemini - Vigilancia Automatica (Watch Mode)

echo ==============================================================================
echo  Conversor Gemini: Vigilancia Automatica Ativa (Watch Mode)
echo ==============================================================================
echo.
echo Monitorando em tempo real:
echo   - 12-conversoes-pdf-md\arquivos-de-entrada\padrao\
echo   - 12-conversoes-pdf-md\arquivos-de-entrada\ocr\
echo   - 12-conversoes-pdf-md\arquivos-de-entrada\anonimizacao\
echo.
echo Basta colar qualquer arquivo nessas pastas para ser convertido automaticamente!
echo Para pausar ou fechar, basta fechar esta janela ou pressionar Ctrl+C.
echo.

python "%~dp0auto_conversor.py" --watch --intervalo 3

pause
