@echo off
setlocal
cd /d "%~dp0"
echo ================================================================
echo  BENCHMARK - IMPORT TURBO v0.3.0.2
echo ================================================================
if not exist ".venv\Scripts\python.exe" (
  echo [ERRO] .venv nao encontrada. Rode EXECUTAR_LOCAL.bat primeiro.
  pause
  exit /b 1
)
set /p ARQUIVO=Arraste o arquivo .sswweb aqui e pressione ENTER: 
set ARQUIVO=%ARQUIVO:"=%
if not exist "%ARQUIVO%" (
  echo [ERRO] Arquivo nao encontrado: %ARQUIVO%
  pause
  exit /b 1
)
set SSW_IMPORT_ENGINE=v2
".venv\Scripts\python.exe" manage.py benchmark_ssw_import "%ARQUIVO%" --repeat 3
pause
endlocal
