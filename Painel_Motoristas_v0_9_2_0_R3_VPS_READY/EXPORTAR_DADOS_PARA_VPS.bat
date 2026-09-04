@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\export-vps-data.ps1"
if errorlevel 1 (
  echo.
  echo ERRO ao exportar dados para VPS.
  pause
  exit /b 1
)
echo.
echo Exportacao concluida.
pause
