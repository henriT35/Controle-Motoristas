@echo off
setlocal
cd /d "%~dp0"
echo ================================================================
echo  VERIFICACAO - IMPORT TURBO v0.3.0.2
echo ================================================================
if not exist ".venv\Scripts\python.exe" (
  echo [ERRO] .venv nao encontrada. Rode EXECUTAR_LOCAL.bat primeiro.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" manage.py shell -c "import os; from apps.ssw.import_engine_v2 import IMPORT_ENGINE_BUILD; from apps.ssw.progress import PROGRESS_BUILD; print('Import Engine :', IMPORT_ENGINE_BUILD); print('Progress      :', PROGRESS_BUILD); print('Engine ativo  :', os.getenv('SSW_IMPORT_ENGINE','v2')); print('Esperado      : v2')"
echo.
echo Se aparecer 0.3.0.2-turbo e Engine ativo v2, o motor novo esta carregado.
pause
endlocal
