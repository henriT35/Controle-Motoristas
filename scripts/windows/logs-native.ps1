. (Join-Path $PSScriptRoot "common-native.ps1")
$Root = Get-Root
$outLog = Join-Path $Root "local_data\logs\server.out.log"
$errLog = Join-Path $Root "local_data\logs\server.err.log"
Write-Host "=== ERROS ===" -ForegroundColor Red
if (Test-Path $errLog) { Get-Content $errLog -Tail 120 } else { Write-Host "Sem log de erro ainda." }
Write-Host "`n=== SAIDA ===" -ForegroundColor Cyan
if (Test-Path $outLog) { Get-Content $outLog -Tail 120 } else { Write-Host "Sem log de saida ainda." }
Write-Host "`nPressione ENTER para fechar..." -ForegroundColor DarkGray
[void](Read-Host)
