@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" manage.py reconcile_ssw_proofs --apply
) else (
  python manage.py reconcile_ssw_proofs --apply
)
echo.
pause
