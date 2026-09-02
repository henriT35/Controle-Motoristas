$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common-native.ps1")
$Root = Get-Root
Set-Location $Root

$envPath = Join-Path $Root ".env.local"
$mode = "sqlite"
if (Test-Path $envPath) {
    $line = Select-String -Path $envPath -Pattern '^DATABASE_MODE=(.+)$' | Select-Object -First 1
    if ($line) { $mode = $line.Matches[0].Groups[1].Value.Trim().ToLower() }
}

if ($mode -ne "sqlite") {
    Write-Host "O projeto esta configurado para PostgreSQL." -ForegroundColor Yellow
    Write-Host "Por seguranca, este atalho nao apaga um banco PostgreSQL automaticamente." -ForegroundColor Yellow
    Write-Host "Se quiser voltar ao banco local rapido, renomeie/remova .env.local e execute EXECUTAR_LOCAL.bat." -ForegroundColor White
    Read-Host "Pressione ENTER para fechar"
    exit 0
}

Write-Host "ATENCAO: isto apagara TODOS os dados do banco local rapido." -ForegroundColor Red
$answer = Read-Host "Digite APAGAR para confirmar"
if ($answer -ne "APAGAR") { Write-Host "Cancelado." -ForegroundColor Yellow; exit 0 }

& (Join-Path $PSScriptRoot "stop-native.ps1")
$db = Join-Path $Root "local_data\painel_motoristas.sqlite3"
if (Test-Path $db) { Remove-Item $db -Force }
Write-Host "Banco local removido. Execute EXECUTAR_LOCAL.bat para recriar." -ForegroundColor Green
Read-Host "Pressione ENTER para fechar"
