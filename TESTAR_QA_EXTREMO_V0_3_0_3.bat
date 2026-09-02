@echo off
setlocal
cd /d "%~dp0"
set PY=.venv\Scripts\python.exe
if not exist "%PY%" (
  echo [ERRO] .venv nao encontrado. Rode EXECUTAR_LOCAL.bat primeiro.
  pause
  exit /b 1
)

echo ==============================================================
echo  QA EXTREMO - PAINEL MOTORISTAS v0.3.0.3
echo ==============================================================
echo.

echo [1/4] Django check...
"%PY%" manage.py check
if errorlevel 1 goto :fail

echo.
echo [2/4] Testes de regressao e idempotencia...
"%PY%" manage.py test apps.ssw.tests apps.ssw.tests_extreme apps.operations.tests apps.proofs.tests apps.core.tests apps.bugs.tests apps.reports.tests --verbosity 2
if errorlevel 1 goto :fail

echo.
echo [3/4] Auditoria de integridade do banco atual (somente leitura)...
"%PY%" manage.py qa_ssw_integrity
if errorlevel 1 goto :fail

echo.
echo [4/4] Healthcheck...
"%PY%" manage.py healthcheck
if errorlevel 1 goto :fail

echo.
echo [OK] QA automatizado concluiu sem falhas.
echo Para testar 10 importacoes do mesmo arquivo com ROLLBACK seguro,
echo execute TESTAR_REPETICAO_SSW_V0_3_0_3.bat.
pause
exit /b 0

:fail
echo.
echo [FALHA] Um ou mais testes falharam. Nao homologue esta versao ainda.
pause
exit /b 1
