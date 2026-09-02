@echo off
setlocal
cd /d "%~dp0"

echo ===============================================
echo PAINEL MOTORISTAS - VERIFICAR BUILD V0.3.0.10
echo ===============================================

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\verify_build_v0310.py
) else (
    py -3 scripts\verify_build_v0310.py 2>nul
    if errorlevel 1 python scripts\verify_build_v0310.py
)

set RC=%ERRORLEVEL%
echo.
if not "%RC%"=="0" (
    echo VERIFICACAO FALHOU. Nao rode importacao antes de revisar o resultado acima.
) else (
    echo VERIFICACAO CONCLUIDA COM SUCESSO.
)
pause
exit /b %RC%
