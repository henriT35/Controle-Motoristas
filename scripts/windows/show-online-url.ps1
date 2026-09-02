. (Join-Path $PSScriptRoot "common-native.ps1")
$Root = Get-Root
$urlFile = Join-Path $Root "local_data\online_url.txt"
if (-not (Test-Path $urlFile)) {
    Write-Host "Nenhuma URL online ativa foi encontrada." -ForegroundColor Yellow
    Write-Host "Execute EXECUTAR_ONLINE.bat primeiro." -ForegroundColor Cyan
    Start-Sleep -Seconds 3
    exit 1
}
$url = (Get-Content $urlFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
Write-Host "URL publica atual:" -ForegroundColor Cyan
Write-Host $url -ForegroundColor White
try { Set-Clipboard -Value $url; Write-Host "`nCopiada para a area de transferencia." -ForegroundColor Green } catch {}
Start-Process ($url + "/login/")
Start-Sleep -Seconds 3
