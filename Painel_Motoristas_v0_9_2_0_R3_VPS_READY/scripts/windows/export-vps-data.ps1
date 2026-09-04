$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    if (Get-Command python -ErrorAction SilentlyContinue) { $Python = "python" }
    else { throw "Python/.venv nao encontrado. Rode o Painel localmente antes de exportar." }
}

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutDir = Join-Path $Root "local_data\vps_transfer_$Stamp"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$Fixture = Join-Path $OutDir "painel_data.json"

Write-Host "==> Validando projeto" -ForegroundColor Cyan
& $Python manage.py check
if ($LASTEXITCODE -ne 0) { throw "manage.py check falhou" }

Write-Host "==> Exportando banco via Django dumpdata" -ForegroundColor Cyan
& $Python manage.py dumpdata `
  --natural-foreign `
  --natural-primary `
  --exclude contenttypes `
  --exclude auth.permission `
  --exclude admin.logentry `
  --exclude sessions `
  --indent 2 `
  --output $Fixture
if ($LASTEXITCODE -ne 0) { throw "dumpdata falhou" }

$MediaArchive = Join-Path $OutDir "media.tar.gz"
if (Test-Path (Join-Path $Root "media")) {
    Write-Host "==> Empacotando media" -ForegroundColor Cyan
    tar -czf $MediaArchive -C $Root media
}

$Readme = @"
TRANSFERENCIA PARA VPS - $Stamp

1. painel_data.json
   Dados do Django exportados do ambiente local.
   O arquivo pode conter dados operacionais e hashes de senha. Trate como sensivel.

2. media.tar.gz (se existir)
   Uploads/evidencias do Painel.

NA VPS, depois de instalar a MESMA versao:
  bash deploy/vps/import_fixture.sh /caminho/painel_data.json

Para restaurar media:
  docker compose cp media.tar.gz web:/tmp/media.tar.gz
  docker compose exec -T web sh -lc 'cd /app && tar -xzf /tmp/media.tar.gz && rm /tmp/media.tar.gz'

A sessao WhatsApp/Baileys NAO e exportada por seguranca.
Faca um novo pareamento na VPS.
"@
Set-Content -Path (Join-Path $OutDir "LEIA_ME.txt") -Value $Readme -Encoding UTF8

Get-FileHash -Algorithm SHA256 $Fixture | ForEach-Object {
    "$($_.Hash.ToLower())  painel_data.json"
} | Set-Content -Path (Join-Path $OutDir "SHA256SUMS.txt") -Encoding ascii
if (Test-Path $MediaArchive) {
    Get-FileHash -Algorithm SHA256 $MediaArchive | ForEach-Object {
        "$($_.Hash.ToLower())  media.tar.gz"
    } | Add-Content -Path (Join-Path $OutDir "SHA256SUMS.txt") -Encoding ascii
}

Write-Host "" 
Write-Host "Exportacao criada em:" -ForegroundColor Green
Write-Host $OutDir -ForegroundColor Green
Write-Host "NAO envie esta pasta para o GitHub." -ForegroundColor Yellow
