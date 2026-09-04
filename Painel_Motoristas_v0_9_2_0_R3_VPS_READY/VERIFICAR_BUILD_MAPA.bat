@echo off
setlocal
cd /d "%~dp0"

echo ==================================================
echo PAINEL MOTORISTAS - VERIFICAR MAPA V0.4.0.1
echo ==================================================

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\verify_build_map_v0401.py
) else (
    py -3 scripts\verify_build_map_v0401.py 2>nul
    if errorlevel 1 python scripts\verify_build_map_v0401.py
)

set RC=%ERRORLEVEL%
echo.
if not "%RC%"=="0" (
    echo VERIFICACAO FALHOU. Revise o resultado antes de homologar o mapa.
) else (
    echo VERIFICACAO CONCLUIDA.
)
pause
exit /b %RC%
