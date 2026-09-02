@echo off
setlocal
cd /d "%~dp0"
echo ================================================================
echo  PAINEL MOTORISTAS V0.3.0 - PERFORMANCE QA
echo ================================================================
if not exist ".venv\Scripts\python.exe" (
  echo [ERRO] Ambiente .venv nao encontrado. Execute EXECUTAR_LOCAL.bat primeiro.
  pause
  exit /b 1
)
.venv\Scripts\python.exe scripts\qa\test_performance_static.py
if errorlevel 1 goto :erro
.venv\Scripts\python.exe manage.py healthcheck
if errorlevel 1 goto :erro
.venv\Scripts\python.exe manage.py benchmark_system --repeat 3
if errorlevel 1 goto :erro
echo.
echo QA e benchmark web concluidos.
pause
exit /b 0
:erro
echo.
echo [ERRO] Algum teste de performance falhou.
pause
exit /b 1
