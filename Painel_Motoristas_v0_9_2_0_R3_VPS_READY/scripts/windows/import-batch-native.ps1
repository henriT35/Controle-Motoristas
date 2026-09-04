$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common-native.ps1")
$Root = Get-Root
Set-Location $Root
$Python = Ensure-Venv $Root
Ensure-EnvFile $Root

Ensure-LocalDependencies $Root $Python
& $Python manage.py makemigrations --check --dry-run *> $null
if ($LASTEXITCODE -ne 0) { Fail "Falha ao preparar migrations." }
& $Python manage.py migrate --fake-initial --noinput *> $null
if ($LASTEXITCODE -ne 0) { Fail "Falha ao atualizar o banco." }
& $Python manage.py bootstrap_local *> $null

Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = "Selecione a pasta com os relatórios mensais do SSW (.sswweb/.csv)"
$dialog.ShowNewFolderButton = $false
if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
    Write-Host "Importacao em lote cancelada." -ForegroundColor Yellow
    exit 0
}

$folder = $dialog.SelectedPath
Write-Host "`nImportando relatórios da pasta:" -ForegroundColor Cyan
Write-Host $folder -ForegroundColor White
Write-Host "Os arquivos serao ordenados pelo periodo detectado no proprio relatorio." -ForegroundColor DarkGray
Write-Host "Se um arquivo falhar, os demais continuam e o erro fica registrado." -ForegroundColor DarkGray

& $Python manage.py import_ssw_batch $folder --kind MANUAL
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    Write-Host "`nO lote terminou com um ou mais erros. As importacoes concluídas foram preservadas." -ForegroundColor Yellow
    Write-Host "Consulte Importacoes SSW / Historico ou VER_LOGS_LOCAL.bat." -ForegroundColor Yellow
} else {
    Write-Host "`nIMPORTACAO EM LOTE CONCLUIDA." -ForegroundColor Green
}

Start-Process "http://127.0.0.1:8000/ssw/importacoes/"
Write-Host "`nPressione ENTER para fechar..." -ForegroundColor DarkGray
[void](Read-Host)
exit $exitCode
