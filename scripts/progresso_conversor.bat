@echo off
chcp 65001 > nul
title Conversor Gemini - Progresso em Tempo Real

python "%~dp0auto_conversor.py" --progresso

echo.
pause
