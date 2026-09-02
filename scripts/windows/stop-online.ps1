$ErrorActionPreference = "SilentlyContinue"
. (Join-Path $PSScriptRoot "common-native.ps1")
$Root = Get-Root
$localData = Join-Path $Root "local_data"

$stopped = $false
foreach ($pidName in @("cloudflared.pid", "server.pid")) {
    $pidPath = Join-Path $localData $pidName
    if (Test-Path $pidPath) {
        $pidValue = Get-Content $pidPath -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($pidValue) {
            $p = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
            if ($p) {
                Write-Host "Parando processo $pidValue..." -ForegroundColor Cyan
                & taskkill /PID $pidValue /T /F *> $null
                $stopped = $true
            }
        }
        Remove-Item $pidPath -Force -ErrorAction SilentlyContinue
    }
}
Remove-Item (Join-Path $localData "online_url.txt") -Force -ErrorAction SilentlyContinue
if ($stopped) {
    Write-Host "Painel online e Cloudflare Tunnel encerrados." -ForegroundColor Green
} else {
    Write-Host "Nenhum processo online registrado como ativo." -ForegroundColor Yellow
}
Start-Sleep -Seconds 2
