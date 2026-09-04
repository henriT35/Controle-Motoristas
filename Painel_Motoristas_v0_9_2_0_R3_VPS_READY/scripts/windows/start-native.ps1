$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common-native.ps1")
$Root = Get-Root
Set-Location $Root

Write-Host "===============================================" -ForegroundColor Blue
Write-Host " PAINEL MOTORISTAS - LOCAL SEM DOCKER" -ForegroundColor White
Write-Host "===============================================" -ForegroundColor Blue

# v0.3.0.1: nunca aplique migrations por baixo de um Django antigo ainda vivo.
# Um processo antigo mantém os models carregados em memória e pode tentar inserir
# linhas sem as novas colunas, causando NOT NULL em ssw_importrun.*_seconds.
$tunnelPidFile = Join-Path $Root "local_data\cloudflared.pid"
if (Test-Path $tunnelPidFile) {
    $tunnelPid = Get-Content $tunnelPidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($tunnelPid -and (Get-Process -Id $tunnelPid -ErrorAction SilentlyContinue)) {
        Write-Host "`n==> Encerrando Cloudflare Tunnel anterior antes do modo local (PID $tunnelPid)" -ForegroundColor Yellow
        & taskkill /PID $tunnelPid /T /F *> $null
        Start-Sleep -Milliseconds 600
    }
    Remove-Item $tunnelPidFile -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $Root "local_data\online_url.txt") -Force -ErrorAction SilentlyContinue
}

$schedulerPidFile = Join-Path $Root "local_data\scheduler.pid"
if (Test-Path $schedulerPidFile) {
    $schedulerPid = Get-Content $schedulerPidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($schedulerPid -and (Get-Process -Id $schedulerPid -ErrorAction SilentlyContinue)) {
        Write-Host "`n==> Reiniciando scheduler SSW existente (PID $schedulerPid)" -ForegroundColor Yellow
        & taskkill /PID $schedulerPid /T /F *> $null
        Start-Sleep -Milliseconds 500
    }
    Remove-Item $schedulerPidFile -Force -ErrorAction SilentlyContinue
}

$pidFile = Join-Path $Root "local_data\server.pid"
if (Test-Path $pidFile) {
    $oldPid = Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($oldPid) {
        $old = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
        if ($old) {
            Write-Host "`n==> Reiniciando servidor existente para aplicar o codigo/migrations com seguranca (PID $oldPid)" -ForegroundColor Yellow
            Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 800
        }
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

$Python = Ensure-Venv $Root
Ensure-EnvFile $Root
New-Item -ItemType Directory -Force -Path (Join-Path $Root "local_data") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Root "local_data\logs") | Out-Null


Write-Host "`n==> Instalando/verificando dependencias" -ForegroundColor Cyan
Ensure-LocalDependencies $Root $Python

Write-Host "`n==> Validando migrations versionadas" -ForegroundColor Cyan
& $Python manage.py makemigrations --check --dry-run
if ($LASTEXITCODE -ne 0) { Fail "Models e migrations divergiram. Nao gere migration automaticamente em producao." }

Write-Host "`n==> Atualizando banco local" -ForegroundColor Cyan
& $Python manage.py migrate --fake-initial --noinput
if ($LASTEXITCODE -ne 0) { Fail "Falha ao atualizar o banco local." }

Write-Host "`n==> Sincronizando avaliacao V3, historico de retiradas e snapshots" -ForegroundColor Cyan
& $Python manage.py reconcile_retained_proofs --apply --quiet
if ($LASTEXITCODE -ne 0) { Fail "Falha ao reconciliar comprovantes pelo estado atual do SSW." }
& $Python manage.py sync_driver_evaluation_events --quiet
if ($LASTEXITCODE -ne 0) { Fail "Falha ao sincronizar eventos de avaliacao V3." }

# Marcador de sessao para o diagnostico nao misturar tempos de execucoes antigas.
$perfLog = Join-Path $Root "local_data\logs\painel.log"
$perfStamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss,fff"
Add-Content -Path $perfLog -Value ("$perfStamp INFO apps.performance: PERF session.start mode=local pid=$PID") -Encoding UTF8

Write-Host "`n==> Preparando usuario administrador" -ForegroundColor Cyan
& $Python manage.py bootstrap_local
if ($LASTEXITCODE -ne 0) { Fail "Falha ao criar/preparar o usuario administrador." }

$outLog = Join-Path $Root "local_data\logs\server.out.log"
$errLog = Join-Path $Root "local_data\logs\server.err.log"
Write-Host "`n==> Iniciando servidor Django local" -ForegroundColor Cyan
$p = Start-Process -FilePath $Python -ArgumentList @("manage.py","runserver","127.0.0.1:8000","--noreload") -WorkingDirectory $Root -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru -WindowStyle Hidden
Set-Content -Path $pidFile -Value $p.Id -Encoding ASCII

Write-Host "`n==> Aguardando http://127.0.0.1:8000" -ForegroundColor Cyan
$ready = $false
for ($i=0; $i -lt 45; $i++) {
    if ($p.HasExited) { break }
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/login/" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { $ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 1
}

if (-not $ready) {
    Write-Host "`nO servidor nao respondeu. Abra VER_LOGS_LOCAL.bat para ver o erro." -ForegroundColor Red
    if (Test-Path $errLog) { Get-Content $errLog -Tail 30 }
    Write-Host "`nPressione ENTER para fechar..." -ForegroundColor DarkGray
    [void](Read-Host)
    exit 1
}

$schedulerOut = Join-Path $Root "local_data\logs\scheduler.out.log"
$schedulerErr = Join-Path $Root "local_data\logs\scheduler.err.log"
Write-Host "`n==> Iniciando scheduler automatico do robo SSW" -ForegroundColor Cyan
$scheduler = Start-Process -FilePath $Python -ArgumentList @("manage.py","run_ssw_scheduler","--poll-seconds","30") -WorkingDirectory $Root -RedirectStandardOutput $schedulerOut -RedirectStandardError $schedulerErr -PassThru -WindowStyle Hidden
Set-Content -Path $schedulerPidFile -Value $scheduler.Id -Encoding ASCII
Start-Sleep -Seconds 2
if ($scheduler.HasExited) {
    if (Test-Path $schedulerErr) { Get-Content $schedulerErr -Tail 30 }
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    Fail "O scheduler SSW nao conseguiu iniciar."
}

Write-Host "`nSISTEMA PRONTO!" -ForegroundColor Green
Write-Host "Endereco : http://127.0.0.1:8000/login/" -ForegroundColor White
Write-Host "Usuario  : admin" -ForegroundColor White
Write-Host "Senha    : Painel@2026!" -ForegroundColor White
Write-Host "Scheduler: ativo (PID $($scheduler.Id))" -ForegroundColor Green
Write-Host "Banco    : modo local rapido (SQLite)." -ForegroundColor Gray
Write-Host "           Para PostgreSQL local, use CONFIGURAR_POSTGRESQL_LOCAL.bat." -ForegroundColor Gray
Start-Process "http://127.0.0.1:8000/login/"
Write-Host "`nPode fechar esta janela. O servidor continua rodando." -ForegroundColor DarkGray
Write-Host "Para parar, use PARAR_LOCAL.bat." -ForegroundColor Cyan
Start-Sleep -Seconds 4
