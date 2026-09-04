$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common-native.ps1")
$Root = Get-Root
Set-Location $Root
$Python = Ensure-Venv $Root
Ensure-EnvFile $Root
Write-Host "==> Preparando Playwright (uso opcional para homologacao)" -ForegroundColor Cyan
& $Python -m pip install --disable-pip-version-check -q playwright
if ($LASTEXITCODE -ne 0) { Fail "Falha ao instalar Playwright." }
& $Python -m playwright install chromium
if ($LASTEXITCODE -ne 0) { Fail "Falha ao instalar Chromium do Playwright." }
Write-Host "==> Capturando 12 telas em 1672x941" -ForegroundColor Cyan
& $Python (Join-Path $Root "scripts\capture_screens.py")
if ($LASTEXITCODE -ne 0) { Fail "Falha na captura. Confirme que EXECUTAR_LOCAL.bat esta rodando." }
Write-Host "Capturas concluidas em docs\homologacao\v0_2_2" -ForegroundColor Green
Read-Host "Pressione ENTER para fechar"
