@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "PY=python"
set "PYTHONDONTWRITEBYTECODE=1"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
set FAIL=0
set RUNTIME_PENDING=0

echo ============================================================
echo PAINEL MOTORISTAS - VERIFICADOR v0.9.2.0
echo ============================================================
if exist VERSION.txt (
  set /p VERSION=<VERSION.txt
  echo VERSION: !VERSION!
  if /i not "!VERSION!"=="0.9.2.0" (
    echo [FAIL] VERSION.txt nao corresponde a v0.9.2.0.
    set FAIL=1
  )
) else (
  echo [FAIL] VERSION.txt ausente.
  set FAIL=1
)

echo.
echo [1/8] Python / QA portatil / core homologado
%PY% --version || set FAIL=1
%PY% scripts\qa\portable_qa.py
if errorlevel 1 (echo [FAIL] portable_qa & set FAIL=1) else echo [PASS] sintaxe Python + invariantes do importador + core SSW

echo.
echo [2/8] Performance estatica e formula da avaliacao V3
%PY% scripts\qa\test_performance_static.py
if errorlevel 1 (echo [FAIL] performance_static & set FAIL=1) else echo [PASS] performance_static
%PY% scripts\qa\test_performance_formula.py
if errorlevel 1 (echo [FAIL] performance_formula & set FAIL=1) else echo [PASS] performance_formula
%PY% scripts\qa\test_v091_contract_static.py
if errorlevel 1 (echo [FAIL] contrato_v091 & set FAIL=1) else echo [PASS] contrato_v091
%PY% scripts\qa\test_v092_contract_static.py
if errorlevel 1 (echo [FAIL] contrato_v092 & set FAIL=1) else echo [PASS] contrato_v092
%PY% scripts\qa\test_v092_formula.py
if errorlevel 1 (echo [FAIL] formula_v092 & set FAIL=1) else echo [PASS] formula_v092
%PY% scripts\qa\test_migrations_v091_static.py
if errorlevel 1 (echo [FAIL] migrations_v091_static & set FAIL=1) else echo [PASS] migrations_v091_static

echo.
echo [3/8] Adapter/contrato do robo homologado
%PY% scripts\qa\test_robot_adapter.py
if errorlevel 1 (echo [FAIL] robot_adapter & set FAIL=1) else echo [PASS] robot_adapter

echo.
echo [4/8] Templates / rotas estaticas
%PY% scripts\qa\test_template_routes_static.py
if errorlevel 1 (echo [FAIL] template_routes_static & set FAIL=1) else echo [PASS] template_routes_static

echo.
echo [5/8] JavaScript
where node >nul 2>nul
if errorlevel 1 (
  echo [SKIP/ATENCAO] Node.js nao encontrado. JS precisa ser validado antes da homologacao.
  set RUNTIME_PENDING=1
) else (
  set JSFAIL=0
  for /r static %%F in (*.js) do (
    node --check "%%F" >nul 2>nul
    if errorlevel 1 (
      echo [FAIL] %%~fF
      set JSFAIL=1
    )
  )
  if !JSFAIL! EQU 1 (set FAIL=1) else echo [PASS] Todos os JavaScript em static passaram no node --check
)

echo.
echo [6/8] Django / migrations / testes criticos
%PY% -c "import django; print('Django', django.get_version())" >nul 2>nul
if errorlevel 1 (
  echo [SKIP/ATENCAO] Django nao esta instalado neste Python.
  echo Prepare a .venv real e rode este verificador novamente antes de homologar.
  set RUNTIME_PENDING=1
) else (
  %PY% manage.py check
  if errorlevel 1 (echo [FAIL] manage.py check & set FAIL=1) else echo [PASS] manage.py check

  %PY% manage.py makemigrations --check --dry-run
  if errorlevel 1 (
    echo [FAIL] Ha migrations ainda nao versionadas.
    echo Nao gere migrations automaticamente em producao.
    echo Gere/revise em desenvolvimento, aplique em BANCO DE HOMOLOGACAO e rode novamente.
    set FAIL=1
  ) else (
    echo [PASS] Nenhuma migration pendente.
    %PY% manage.py migrate --plan
    if errorlevel 1 (echo [FAIL] migrate --plan & set FAIL=1) else echo [PASS] migrate --plan
  )

  %PY% manage.py test apps.core.tests apps.ssw.tests apps.operations.tests apps.operations.tests_geo apps.dashboard.tests apps.proofs.tests apps.drivers.tests apps.reports.tests --verbosity 1
  if errorlevel 1 (echo [FAIL] Testes Django criticos & set FAIL=1) else echo [PASS] Testes Django criticos
)

echo.
echo [7/8] Arquivos proibidos na distribuicao
set BAD=0
for /r %%F in (*.sqlite3 *.db *.log *.pyc) do (
  echo %%~fF | findstr /i /c:"\.venv\" >nul
  if errorlevel 1 (
    echo [FAIL] Artefato local: %%~fF
    set BAD=1
  )
)
for /d /r %%D in (__pycache__) do (
  echo %%~fD | findstr /i /c:"\.venv\" >nul
  if errorlevel 1 (
    echo [FAIL] Cache Python: %%~fD
    set BAD=1
  )
)
if exist ".env" (echo [FAIL] .env real presente & set BAD=1)
if exist "robot_ssw\credenciais.local.json" (echo [FAIL] credenciais.local.json presente & set BAD=1)
if !BAD! EQU 1 (set FAIL=1) else echo [PASS] Nenhum artefato local proibido detectado.

echo.
echo [8/8] Estrutura essencial
for %%F in (README.md CHANGELOG.md VERSION VERSION.txt requirements.txt manage.py RELEASE_MANIFEST.txt docs\QA_RELEASE.md docs\QA_RELEASE_V0_9_2_0.md docs\RANKING_V3.md docs\PORTAL_MOTORISTA.md docs\ROTINAS_SSW.md docs\PERFORMANCE.md docs\VPS_HOSTINGER_GITHUB.md docs\REGRAS_PARA_PROXIMO_AGENTE.md docs\AVALIACAO_V3_EXPLICAVEL.md docs\VALIDACAO_ROM13.md docs\REGULARIDADE.md docs\RETENCOES_SSW.md CONTEXTO_MESTRE_PROXIMO_CHAT_PAINEL_MOTORISTAS_v0_9_2_0.md INSTALAR_BOT_WHATSAPP.bat INICIAR_BOT_WHATSAPP.bat) do (
  if not exist "%%F" (
    echo [FAIL] Arquivo essencial ausente: %%F
    set FAIL=1
  )
)
if !FAIL! EQU 0 echo [PASS] Estrutura essencial presente.

echo.
if !FAIL! NEQ 0 (
  echo ============================================================
  echo BUILD COM FALHAS - veja FAIL/PENDENTE acima
  echo ============================================================
  exit /b 1
)

if !RUNTIME_PENDING! NEQ 0 (
  echo ============================================================
  echo QA PORTATIL PASS - HOMOLOGACAO DE RUNTIME AINDA PENDENTE
  echo Rode novamente com .venv/Django/Node completos antes de promover.
  echo ============================================================
  exit /b 2
)

echo ============================================================
echo BUILD VERIFICADA NO AMBIENTE COMPLETO - pronta para homologacao funcional
echo ============================================================
exit /b 0
