@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\start-whatsapp-baileys.ps1"
if errorlevel 1 (
  echo.
  echo Nao foi possivel iniciar o WhatsApp. Rode INSTALAR_BOT_WHATSAPP.bat primeiro.
)
pause
