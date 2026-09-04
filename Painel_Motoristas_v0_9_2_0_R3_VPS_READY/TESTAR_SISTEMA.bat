@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Execute EXECUTAR_LOCAL.bat primeiro.
  pause
  exit /b 1
)
echo ===============================================
echo  PAINEL MOTORISTAS - TESTES AUTOMATIZADOS
echo ===============================================
".venv\Scripts\python.exe" manage.py check
if errorlevel 1 goto :erro
".venv\Scripts\python.exe" manage.py test
if errorlevel 1 goto :erro
echo.
echo TESTES CONCLUIDOS COM SUCESSO.
pause
exit /b 0
:erro
echo.
echo ALGUM TESTE FALHOU. Veja a mensagem acima.
pause
exit /b 1
