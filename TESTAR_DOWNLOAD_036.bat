@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo ATENCAO: este teste acessa o SSW real e solicita/baixa um relatorio 036.
set /p CONF=Digite SIM para continuar: 
if /I not "%CONF%"=="SIM" exit /b 2
if not exist ".venv\Scripts\python.exe" (echo .venv nao encontrada.& pause& exit /b 1)
pushd robot_ssw
"..\.venv\Scripts\python.exe" diagnostics_real.py --stage download
set RC=%ERRORLEVEL%
popd
pause
exit /b %RC%
