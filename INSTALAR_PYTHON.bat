@echo off
setlocal
where winget >nul 2>nul
if errorlevel 1 (
  echo Winget nao encontrado. Instale Python 3.12 manualmente em https://www.python.org/
  pause
  exit /b 1
)
echo Instalando Python 3.12...
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
  echo Falha na instalacao. Verifique a mensagem acima.
  pause
  exit /b 1
)
echo.
echo Python instalado. Feche esta janela e execute EXECUTAR_LOCAL.bat novamente.
pause
