@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY where py >nul 2>&1 && set "PY=py"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
  echo [ERRO] Python nao encontrado. Execute EXECUTAR_LOCAL.bat primeiro.
  pause
  exit /b 1
)

%PY% "scripts\robot_credentials.py" configure
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
  echo [ERRO] Nao foi possivel atualizar as credenciais.
  pause
  exit /b %RC%
)
call VERIFICAR_CREDENCIAIS_SSW.bat
exit /b %ERRORLEVEL%
