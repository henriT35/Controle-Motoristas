@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (set PY=.venv\Scripts\python.exe) else (set PY=python)
%PY% manage.py ssw_queue_control status
%PY% manage.py ssw_queue_control resume
pause
