@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo ================================================================
echo  PREPARAR ROBO SSW HOMOLOGADO - P13.1
echo ================================================================

if not exist ".venv\Scripts\python.exe" (
  echo [ERRO] .venv nao encontrada.
  echo Execute EXECUTAR_LOCAL.bat primeiro e tente novamente.
  pause
  exit /b 1
)

if not exist "robot_ssw" mkdir "robot_ssw" >nul 2>&1

rem Hotfix: recria o requirements do robo quando ausente.
if not exist "robot_ssw\requirements.txt" (
  echo [AVISO] robot_ssw\requirements.txt nao encontrado.
  echo Recriando automaticamente...
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$p='robot_ssw\requirements.txt'; $c=@('playwright==1.62.0','python-dotenv>=1.0,<2.0'); [IO.File]::WriteAllLines($p,$c,(New-Object Text.UTF8Encoding($false)))"
  if errorlevel 1 goto :erro_req
)

echo.
echo [1/4] Instalando dependencias do robo...
".venv\Scripts\python.exe" -m pip install -r "robot_ssw\requirements.txt"
if errorlevel 1 (
  echo [AVISO] Instalacao por requirements falhou. Tentando instalacao direta...
  ".venv\Scripts\python.exe" -m pip install "playwright==1.62.0" "python-dotenv>=1.0,<2.0"
  if errorlevel 1 goto :erro
)

echo.
echo [2/4] Validando imports Python...
".venv\Scripts\python.exe" -c "from playwright.sync_api import sync_playwright; import dotenv; print('Playwright/Python-dotenv: OK')"
if errorlevel 1 goto :erro

echo.
echo [3/4] Instalando/validando Chromium do Playwright...
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 goto :erro

echo.
echo [4/4] Conferindo arquivos do core homologado...
if not exist "robot_ssw\robot_ssw\worker.py" (
  echo [ERRO] Core homologado incompleto: robot_ssw\robot_ssw\worker.py nao encontrado.
  echo Reaplique o patch p13 antes de continuar.
  pause
  exit /b 2
)
if not exist "robot_ssw\robot_ssw\__init__.py" (
  echo [ERRO] Core homologado incompleto: __init__.py nao encontrado.
  echo Reaplique o patch p13 antes de continuar.
  pause
  exit /b 2
)

echo.
echo ================================================================
echo  PREPARACAO CONCLUIDA
 echo ================================================================
echo Dependencias: OK
echo Playwright:   OK
echo Chromium:     OK
echo Core p13:     OK
echo.
echo Proximo passo: TESTAR_CORE_ROBO_HOMOLOGADO.bat
pause
exit /b 0

:erro_req
echo.
echo [ERRO] Nao foi possivel recriar robot_ssw\requirements.txt.
pause
exit /b 1

:erro
echo.
echo [ERRO] Falha ao preparar dependencias/Chromium.
echo.
echo Para diagnostico manual, execute:
echo   .venv\Scripts\python.exe -m pip install "playwright==1.62.0" "python-dotenv^>=1.0,^<2.0"
echo   .venv\Scripts\python.exe -m playwright install chromium
pause
exit /b 1
