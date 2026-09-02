@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [ERRO] .venv nao encontrada.
  pause
  exit /b 1
)
echo ================================================================
echo  VERIFICACAO DO BRIDGE P13
 echo ================================================================
".venv\Scripts\python.exe" manage.py shell -c "from apps.ssw.robot_bridge import BRIDGE_BUILD, robot_root, check_robot_ready; print('Bridge carregado     :', BRIDGE_BUILD); print('Diretorio do robo    :', robot_root()); ok,detail=check_robot_ready(launch_browser=False); print('Pronto sem browser   :', 'SIM' if ok else 'NAO'); print('Diagnostico          :', detail)"
echo.
echo Verificando se a mensagem antiga ainda existe no arquivo ativo...
powershell -NoProfile -Command "$p='apps\ssw\robot_bridge.py'; $t=[IO.File]::ReadAllText($p); if($t -match 'Nenhum robô real foi encontrado'){Write-Host 'Bridge antigo detectado: SIM' -ForegroundColor Red}else{Write-Host 'Bridge antigo detectado: NAO' -ForegroundColor Green}"
echo.
pause
