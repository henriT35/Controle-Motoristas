@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo .venv nao encontrada.& pause& exit /b 1)
".venv\Scripts\python.exe" manage.py ssw_robot_doctor
set RC=%ERRORLEVEL%
pause
exit /b %RC%
