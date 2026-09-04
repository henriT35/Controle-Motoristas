@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (set PY=.venv\Scripts\python.exe) else (set PY=python)

echo ================================================================
echo QA - RESILIENCIA ROBO SSW v0.3.0.4
echo ================================================================
%PY% scripts\qa_resilience_v0304.py
if errorlevel 1 goto :erro

echo.
echo Verificando Django...
%PY% manage.py check
if errorlevel 1 goto :erro
%PY% manage.py help run_ssw_robot_guarded >nul
if errorlevel 1 goto :erro
%PY% manage.py help ssw_queue_control >nul
if errorlevel 1 goto :erro
%PY% manage.py help ssw_diagnostic_pack >nul
if errorlevel 1 goto :erro
%PY% manage.py help ssw_reconcile_orphans >nul
if errorlevel 1 goto :erro

echo.
echo PASS - v0.3.0.4 carregada e validada.
goto :fim
:erro
echo.
echo FAIL - revise a saida acima.
:fim
pause
