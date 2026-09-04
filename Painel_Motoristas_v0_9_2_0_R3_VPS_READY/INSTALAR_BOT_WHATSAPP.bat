@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\install-whatsapp-baileys.ps1"
if errorlevel 1 goto :erro
echo.
echo Baileys preparado com sucesso.
pause
exit /b 0
:erro
echo.
echo Falha ao preparar Baileys / Node.js.
echo Confira a internet e tente novamente.
pause
exit /b 1
