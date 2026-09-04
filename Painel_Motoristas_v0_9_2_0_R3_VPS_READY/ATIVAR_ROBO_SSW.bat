@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\windows\robot-toggle.ps1" -Enabled 1
if exist ".venv\Scripts\python.exe" ".venv\Scripts\python.exe" manage.py ssw_robot_doctor
pause
