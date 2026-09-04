@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [ERRO] Execute EXECUTAR_LOCAL.bat primeiro.
  pause
  exit /b 1
)
echo Selecione o relatorio SSW para benchmark. O teste faz ROLLBACK e nao altera o banco.
for /f "usebackq delims=" %%F in (`powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; $d=New-Object System.Windows.Forms.OpenFileDialog; $d.Filter='Relatorio SSW (*.sswweb;*.csv)|*.sswweb;*.csv|Todos (*.*)|*.*'; if($d.ShowDialog() -eq 'OK'){Write-Output $d.FileName}"`) do set "SSWFILE=%%F"
if "%SSWFILE%"=="" exit /b 0
.venv\Scripts\python.exe manage.py benchmark_ssw_import "%SSWFILE%" --repeat 3
pause
