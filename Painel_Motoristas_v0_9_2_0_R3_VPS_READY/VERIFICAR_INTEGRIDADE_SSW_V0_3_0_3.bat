@echo off
setlocal
cd /d "%~dp0"
set PY=.venv\Scripts\python.exe
if not exist "%PY%" (
  echo [ERRO] .venv nao encontrado. Rode EXECUTAR_LOCAL.bat primeiro.
  pause
  exit /b 1
)
"%PY%" manage.py qa_ssw_integrity
set RC=%ERRORLEVEL%
echo.
pause
exit /b %RC%
