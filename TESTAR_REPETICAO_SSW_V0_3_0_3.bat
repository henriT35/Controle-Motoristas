@echo off
setlocal
cd /d "%~dp0"
set PY=.venv\Scripts\python.exe
if not exist "%PY%" (
  echo [ERRO] .venv nao encontrado. Rode EXECUTAR_LOCAL.bat primeiro.
  pause
  exit /b 1
)
set /p FILE=Arraste/cole o caminho do arquivo SSW para testar 10x: 
set FILE=%FILE:"=%
if not exist "%FILE%" (
  echo [ERRO] Arquivo nao encontrado: %FILE%
  pause
  exit /b 1
)
echo.
echo O teste usa transaction rollback. O banco real sera preservado.
"%PY%" manage.py qa_import_idempotency "%FILE%" --repeat 10
set RC=%ERRORLEVEL%
echo.
if %RC%==0 (
  echo [OK] Idempotencia aprovada.
) else (
  echo [FALHA] Divergencia encontrada. Nao homologue antes de corrigir.
)
pause
exit /b %RC%
