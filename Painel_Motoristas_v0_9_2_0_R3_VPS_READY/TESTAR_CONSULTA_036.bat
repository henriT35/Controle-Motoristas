@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo .venv nao encontrada.& pause& exit /b 1)
pushd robot_ssw
"..\.venv\Scripts\python.exe" diagnostics_real.py --stage form
set RC=%ERRORLEVEL%
popd
pause
exit /b %RC%
