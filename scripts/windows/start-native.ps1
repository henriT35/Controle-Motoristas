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

Write-Host "`n==> Verificando modelo de dados" -ForegroundColor Cyan
$modelFiles = Get-ChildItem -Path (Join-Path $Root "apps") -Recurse -Filter "models.py" | Sort-Object FullName
$modelDigestInput = ($modelFiles | ForEach-Object { (Get-FileHash -Algorithm SHA256 $_.FullName).Hash }) -join ""
$sha = [System.Security.Cryptography.SHA256]::Create()
$modelHash = ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($modelDigestInput)))).Replace("-","")
$modelStamp = Join-Path $Root "local_data\models.sha256"
$savedModelHash = if (Test-Path $modelStamp) { Get-Content $modelStamp -ErrorAction SilentlyContinue | Select-Object -First 1 } else { "" }
if ($savedModelHash -ne $modelHash) {
    Write-Host "==> Modelos alterados: gerando migrations uma unica vez" -ForegroundColor Cyan
    & $Python manage.py makemigrations --noinput
    if ($LASTEXITCODE -ne 0) { Fail "Falha ao gerar migrations." }
    Set-Content -Path $modelStamp -Value $modelHash -Encoding ASCII
} else {
    Write-Host "==> Modelos sem alteracao; pulando makemigrations." -ForegroundColor DarkGray
}

Write-Host "`n==> Atualizando banco local" -ForegroundColor Cyan
& $Python manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) { Fail "Falha ao atualizar o banco local." }

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

Write-Host "`nSISTEMA PRONTO!" -ForegroundColor Green
Write-Host "Endereco : http://127.0.0.1:8000/login/" -ForegroundColor White
Write-Host "Usuario  : admin" -ForegroundColor White
Write-Host "Senha    : Painel@2026!" -ForegroundColor White
Write-Host "Banco    : modo local rapido (SQLite)." -ForegroundColor Gray
Write-Host "           Para PostgreSQL local, use CONFIGURAR_POSTGRESQL_LOCAL.bat." -ForegroundColor Gray
Start-Process "http://127.0.0.1:8000/login/"
Write-Host "`nPode fechar esta janela. O servidor continua rodando." -ForegroundColor DarkGray
Write-Host "Para parar, use PARAR_LOCAL.bat." -ForegroundColor Cyan
Start-Sleep -Seconds 4
