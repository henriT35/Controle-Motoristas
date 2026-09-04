$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common-native.ps1")
$Root = Get-Root
Set-Location $Root

Write-Host "===============================================" -ForegroundColor Blue
Write-Host " PAINEL MOTORISTAS - ONLINE SEM DOMINIO" -ForegroundColor White
Write-Host " CLOUDFLARE QUICK TUNNEL + WAITRESS" -ForegroundColor Gray
Write-Host "===============================================" -ForegroundColor Blue

$localData = Join-Path $Root "local_data"
$logsDir = Join-Path $localData "logs"
New-Item -ItemType Directory -Force -Path $localData | Out-Null
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null


# Encerra qualquer servidor/tunel anteriormente iniciado por este pacote.
foreach ($pidName in @("server.pid", "cloudflared.pid", "scheduler.pid")) {
    $pidPath = Join-Path $localData $pidName
    if (Test-Path $pidPath) {
        $oldPid = Get-Content $pidPath -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($oldPid) {
            $old = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
            if ($old) {
                Write-Host "`n==> Encerrando processo anterior $oldPid" -ForegroundColor Yellow
                & taskkill /PID $oldPid /T /F *> $null
                Start-Sleep -Milliseconds 700
            }
        }
        Remove-Item $pidPath -Force -ErrorAction SilentlyContinue
    }
}
Remove-Item (Join-Path $localData "online_url.txt") -Force -ErrorAction SilentlyContinue

$Python = Ensure-Venv $Root
Ensure-EnvFile $Root

Write-Host "`n==> Instalando/verificando dependencias" -ForegroundColor Cyan
Ensure-LocalDependencies $Root $Python

Write-Host "`n==> Validando migrations versionadas" -ForegroundColor Cyan
& $Python manage.py makemigrations --check --dry-run
if ($LASTEXITCODE -ne 0) { Fail "Models e migrations divergiram. Nao gere migration automaticamente em producao." }

Write-Host "`n==> Atualizando banco" -ForegroundColor Cyan
& $Python manage.py migrate --fake-initial --noinput
if ($LASTEXITCODE -ne 0) { Fail "Falha ao atualizar o banco." }

Write-Host "`n==> Sincronizando avaliacao V3, historico de retiradas e snapshots" -ForegroundColor Cyan
& $Python manage.py reconcile_retained_proofs --apply --quiet
if ($LASTEXITCODE -ne 0) { Fail "Falha ao reconciliar comprovantes pelo estado atual do SSW." }
& $Python manage.py sync_driver_evaluation_events --quiet
if ($LASTEXITCODE -ne 0) { Fail "Falha ao sincronizar eventos de avaliacao V3." }

# Marcador de sessao para o diagnostico nao misturar tempos de execucoes antigas.
$perfLog = Join-Path $Root "local_data\logs\painel.log"
$perfStamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss,fff"
Add-Content -Path $perfLog -Value ("$perfStamp INFO apps.performance: PERF session.start mode=online pid=$PID") -Encoding UTF8

Write-Host "`n==> Preparando usuario administrador" -ForegroundColor Cyan
& $Python manage.py bootstrap_local
if ($LASTEXITCODE -ne 0) { Fail "Falha ao criar/preparar o usuario administrador." }

Write-Host "`n==> Protegendo credencial antes de publicar" -ForegroundColor Cyan
& $Python manage.py prepare_online
if ($LASTEXITCODE -ne 0) { Fail "Falha ao preparar a seguranca do modo online." }

# Baixa o executavel oficial somente se ainda nao estiver disponivel.
$toolsDir = Join-Path $Root "tools\cloudflared"
$cloudflared = Join-Path $toolsDir "cloudflared.exe"
if (-not (Test-Path $cloudflared)) {
    $pathCmd = Get-Command cloudflared.exe -ErrorAction SilentlyContinue
    if ($pathCmd) {
        $cloudflared = $pathCmd.Source
    } else {
        New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
        Write-Host "`n==> Baixando cloudflared oficial (Windows 64-bit)" -ForegroundColor Cyan
        $downloadUrl = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
        try {
            Invoke-WebRequest -Uri $downloadUrl -OutFile $cloudflared -UseBasicParsing
        } catch {
            Remove-Item $cloudflared -Force -ErrorAction SilentlyContinue
            Fail "Nao foi possivel baixar o cloudflared. Verifique a internet e tente novamente."
        }
    }
}

try {
    & $cloudflared --version | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "cloudflared invalido" }
} catch {
    Fail "cloudflared nao iniciou corretamente."
}

# Quick Tunnel pode conflitar com config.yaml/config.yml preexistente do usuario.
$cfHome = Join-Path $env:USERPROFILE ".cloudflared"
$existingCfg = @((Join-Path $cfHome "config.yml"), (Join-Path $cfHome "config.yaml")) | Where-Object { Test-Path $_ }
if ($existingCfg.Count -gt 0) {
    Write-Host "`nAVISO: existe configuracao global do cloudflared em $cfHome." -ForegroundColor Yellow
    Write-Host "Quick Tunnel pode nao iniciar enquanto config.yml/config.yaml existir nesse local." -ForegroundColor Yellow
}

$cfOut = Join-Path $logsDir "cloudflared.out.log"
$cfErr = Join-Path $logsDir "cloudflared.err.log"
Remove-Item $cfOut,$cfErr -Force -ErrorAction SilentlyContinue

Write-Host "`n==> Criando endereco publico temporario" -ForegroundColor Cyan
$cf = Start-Process -FilePath $cloudflared -ArgumentList @("tunnel","--url","http://127.0.0.1:8000") -WorkingDirectory $Root -RedirectStandardOutput $cfOut -RedirectStandardError $cfErr -PassThru -WindowStyle Hidden
Set-Content -Path (Join-Path $localData "cloudflared.pid") -Value $cf.Id -Encoding ASCII

$publicUrl = $null
for ($i=0; $i -lt 45; $i++) {
    if ($cf.HasExited) { break }
    $text = ""
    if (Test-Path $cfOut) { $text += (Get-Content $cfOut -Raw -ErrorAction SilentlyContinue) }
    if (Test-Path $cfErr) { $text += "`n" + (Get-Content $cfErr -Raw -ErrorAction SilentlyContinue) }
    $match = [regex]::Match($text, 'https://[a-zA-Z0-9-]+\.trycloudflare\.com')
    if ($match.Success) {
        $publicUrl = $match.Value.TrimEnd('/')
        break
    }
    Start-Sleep -Seconds 1
}

if (-not $publicUrl) {
    & taskkill /PID $cf.Id /T /F *> $null
    Remove-Item (Join-Path $localData "cloudflared.pid") -Force -ErrorAction SilentlyContinue
    Write-Host "`nO Cloudflare nao gerou uma URL publica." -ForegroundColor Red
    if (Test-Path $cfErr) { Get-Content $cfErr -Tail 35 }
    Fail "Falha ao criar Quick Tunnel."
}

Set-Content -Path (Join-Path $localData "online_url.txt") -Value $publicUrl -Encoding ASCII

# Configuracao exclusiva do processo online. Nao altera permanentemente o .env.local.
$env:DJANGO_DEBUG = "0"
$env:DJANGO_ALLOWED_HOSTS = "localhost,127.0.0.1,.trycloudflare.com"
$env:DJANGO_CSRF_TRUSTED_ORIGINS = "https://*.trycloudflare.com"
$env:PANEL_PUBLIC_BASE_URL = $publicUrl
$env:SERVE_PROTECTED_MEDIA = "1"

Write-Host "`n==> Preparando arquivos estaticos" -ForegroundColor Cyan
& $Python manage.py collectstatic --noinput --clear *> $null
if ($LASTEXITCODE -ne 0) { Fail "Falha ao preparar arquivos estaticos." }

$waitress = Join-Path $Root ".venv\Scripts\waitress-serve.exe"
if (-not (Test-Path $waitress)) { Fail "Waitress nao foi instalado corretamente." }

$outLog = Join-Path $logsDir "server.out.log"
$errLog = Join-Path $logsDir "server.err.log"
Write-Host "`n==> Iniciando servidor web" -ForegroundColor Cyan
$server = Start-Process -FilePath $waitress -ArgumentList @("--listen=127.0.0.1:8000","--trusted-proxy=127.0.0.1","config.wsgi:application") -WorkingDirectory $Root -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru -WindowStyle Hidden
Set-Content -Path (Join-Path $localData "server.pid") -Value $server.Id -Encoding ASCII

Write-Host "`n==> Validando servidor local" -ForegroundColor Cyan
$ready = $false
for ($i=0; $i -lt 45; $i++) {
    if ($server.HasExited) { break }
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/login/" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { $ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 1
}
if (-not $ready) {
    & taskkill /PID $cf.Id /T /F *> $null
    Write-Host "`nO servidor nao respondeu. Veja local_data\logs\server.err.log" -ForegroundColor Red
    if (Test-Path $errLog) { Get-Content $errLog -Tail 30 }
    Fail "Falha ao iniciar o Painel online."
}

# v0.8.2.0: no modo Windows nao existe Celery Beat permanente. Este processo
# leve usa a mesma regra do Beat da VPS e mantém as rotinas SSW realmente ativas.
$schedulerOut = Join-Path $logsDir "scheduler.out.log"
$schedulerErr = Join-Path $logsDir "scheduler.err.log"
Write-Host "`n==> Iniciando scheduler automatico do robo SSW" -ForegroundColor Cyan
$scheduler = Start-Process -FilePath $Python -ArgumentList @("manage.py","run_ssw_scheduler","--poll-seconds","30") -WorkingDirectory $Root -RedirectStandardOutput $schedulerOut -RedirectStandardError $schedulerErr -PassThru -WindowStyle Hidden
Set-Content -Path (Join-Path $localData "scheduler.pid") -Value $scheduler.Id -Encoding ASCII
Start-Sleep -Seconds 2
if ($scheduler.HasExited) {
    if (Test-Path $schedulerErr) { Get-Content $schedulerErr -Tail 30 }
    & taskkill /PID $cf.Id /T /F *> $null
    & taskkill /PID $server.Id /T /F *> $null
    Fail "O scheduler SSW nao conseguiu iniciar."
}
Write-Host "Scheduler SSW : ativo (PID $($scheduler.Id))" -ForegroundColor Green

Write-Host "`n==> Validando acesso publico" -ForegroundColor Cyan
$publicReady = $false
for ($i=0; $i -lt 30; $i++) {
    try {
        $response = Invoke-WebRequest -Uri ($publicUrl + "/login/") -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { $publicReady = $true; break }
    } catch {}
    Start-Sleep -Seconds 1
}

Write-Host "`n===============================================" -ForegroundColor Green
Write-Host " PAINEL ONLINE" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
Write-Host "URL publica : $publicUrl" -ForegroundColor White
Write-Host "URL local   : http://127.0.0.1:8000/login/" -ForegroundColor Gray
if (-not $publicReady) {
    Write-Host "Aviso: a URL foi criada, mas a validacao externa ainda nao respondeu." -ForegroundColor Yellow
}

$credPath = Join-Path $localData "ONLINE_ADMIN.txt"
if (Test-Path $credPath) {
    Write-Host "`nCredencial online local:" -ForegroundColor Yellow
    Get-Content $credPath | ForEach-Object { Write-Host $_ -ForegroundColor Yellow }
}

try { Set-Clipboard -Value $publicUrl } catch {}
Write-Host "`nO endereco publico foi copiado para a area de transferencia." -ForegroundColor Cyan
Write-Host "A URL muda quando o Quick Tunnel for recriado." -ForegroundColor Yellow
Write-Host "Para parar servidor + tunel + scheduler, use PARAR_ONLINE.bat." -ForegroundColor Cyan
Start-Process ($publicUrl + "/login/")
Start-Sleep -Seconds 5
