@echo off
setlocal
cd /d "%~dp0"
if not exist manage.py (
  echo Execute este arquivo na raiz do Painel, onde esta o manage.py.
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe (
  echo .venv nao encontrada. Execute EXECUTAR_LOCAL.bat primeiro.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -c "from apps.ssw.robot_bridge import BRIDGE_BUILD; from apps.ssw.robot_service import SERVICE_BUILD, RobotEventPump; print('Bridge:', BRIDGE_BUILD); print('Service:', SERVICE_BUILD); print('EventPump:', 'SIM' if RobotEventPump else 'NAO')"
pause
