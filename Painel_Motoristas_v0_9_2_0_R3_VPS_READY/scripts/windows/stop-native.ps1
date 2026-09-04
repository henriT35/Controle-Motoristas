$ErrorActionPreference = "SilentlyContinue"
. (Join-Path $PSScriptRoot "common-native.ps1")
$Root = Get-Root
$pidFile = Join-Path $Root "local_data\server.pid"
$tunnelPidFile = Join-Path $Root "local_data\cloudflared.pid"
$schedulerPidFile = Join-Path $Root "local_data\scheduler.pid"
if (-not (Test-Path $pidFile) -and -not (Test-Path $tunnelPidFile) -and -not (Test-Path $schedulerPidFile)) {
    Write-Host "Nenhum servidor local/online registrado como ativo." -ForegroundColor Yellow
    Start-Sleep -Seconds 2
    exit 0
}
if (Test-Path $pidFile) {
    $pidValue = Get-Content $pidFile
    $p = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
    if ($p) {
        Write-Host "Parando Painel Motoristas (PID $pidValue)..." -ForegroundColor Cyan
        Stop-Process -Id $pidValue -Force
        Write-Host "Servidor parado. O banco local foi preservado." -ForegroundColor Green
    } else {
        Write-Host "O processo do servidor ja nao estava em execucao." -ForegroundColor Yellow
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}
if (Test-Path $schedulerPidFile) {
    $schedulerPid = Get-Content $schedulerPidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($schedulerPid -and (Get-Process -Id $schedulerPid -ErrorAction SilentlyContinue)) {
        Write-Host "Parando Scheduler SSW (PID $schedulerPid)..." -ForegroundColor Cyan
        & taskkill /PID $schedulerPid /T /F *> $null
    }
    Remove-Item $schedulerPidFile -Force -ErrorAction SilentlyContinue
}
if (Test-Path $tunnelPidFile) {
    $tunnelPid = Get-Content $tunnelPidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($tunnelPid -and (Get-Process -Id $tunnelPid -ErrorAction SilentlyContinue)) {
        Write-Host "Parando Cloudflare Tunnel (PID $tunnelPid)..." -ForegroundColor Cyan
        & taskkill /PID $tunnelPid /T /F *> $null
    }
    Remove-Item $tunnelPidFile -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $Root "local_data\online_url.txt") -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2
