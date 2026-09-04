@echo off
setlocal
cd /d "%~dp0"
echo ===============================================
echo  PAINEL MOTORISTAS - RECONCILIAR LOGICA v0.8.1.0
echo ===============================================
echo.
if not exist ".venv\Scripts\python.exe" (
  echo ERRO: ambiente virtual .venv nao encontrado.
  echo Rode primeiro EXECUTAR_LOCAL.bat ou EXECUTAR_ONLINE.bat.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" manage.py reconcile_operational_logic
if errorlevel 1 (
  echo.
  echo ERRO: reconciliacao falhou. Nenhuma correcao deve ser presumida.
  pause
  exit /b 1
)
echo.
echo Concluido. Abra novamente o Dashboard e a Central de Comprovantes.
pause
