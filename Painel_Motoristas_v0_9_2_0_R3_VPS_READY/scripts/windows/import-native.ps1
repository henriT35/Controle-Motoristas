$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common-native.ps1")
$Root = Get-Root
Set-Location $Root
$Python = Ensure-Venv $Root
Ensure-EnvFile $Root

# Garante dependencias e banco mesmo se o usuario importar antes de abrir a interface.
Ensure-LocalDependencies $Root $Python
& $Python manage.py makemigrations --check --dry-run *> $null
& $Python manage.py migrate --fake-initial --noinput *> $null
& $Python manage.py bootstrap_local *> $null

Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = "Selecione o relatorio de entregas do SSW"
$dialog.Filter = "Relatorio SSW (*.sswweb;*.csv)|*.sswweb;*.csv|Todos os arquivos (*.*)|*.*"
$dialog.Multiselect = $false
if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
    Write-Host "Importacao cancelada." -ForegroundColor Yellow
    exit 0
}

$Inbox = Join-Path $Root "imports\inbox"
New-Item -ItemType Directory -Force -Path $Inbox | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$ext = [System.IO.Path]::GetExtension($dialog.FileName)
$targetName = "ssw_$stamp$ext"
$target = Join-Path $Inbox $targetName
Copy-Item -LiteralPath $dialog.FileName -Destination $target -Force

Write-Host "`nImportando: $($dialog.FileName)" -ForegroundColor Cyan
& $Python manage.py import_ssw $target --kind MANUAL
if ($LASTEXITCODE -ne 0) { Fail "A importacao falhou. Execute VER_LOGS_LOCAL.bat se precisar diagnosticar." }

Write-Host "`nIMPORTACAO CONCLUIDA." -ForegroundColor Green
Start-Process "http://127.0.0.1:8000/dashboard/"
Write-Host "`nPressione ENTER para fechar..." -ForegroundColor DarkGray
[void](Read-Host)
