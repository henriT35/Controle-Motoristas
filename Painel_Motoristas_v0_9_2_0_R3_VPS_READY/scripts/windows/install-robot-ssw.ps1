param(
    [string]$SourcePath = ""
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$RobotDir = Join-Path $Root 'robot_ssw'
$Python = Join-Path $Root '.venv\Scripts\python.exe'

function Write-Step([string]$Text) { Write-Host "[ROBO SSW] $Text" -ForegroundColor Cyan }
function Write-Ok([string]$Text) { Write-Host "[OK] $Text" -ForegroundColor Green }
function Write-Warn([string]$Text) { Write-Host "[ATENCAO] $Text" -ForegroundColor Yellow }

if (-not (Test-Path $Python)) {
    throw 'Ambiente Python local não encontrado. Execute EXECUTAR_LOCAL.bat primeiro.'
}

if ([string]::IsNullOrWhiteSpace($SourcePath)) {
    try {
        Add-Type -AssemblyName System.Windows.Forms
        $dialog = New-Object System.Windows.Forms.OpenFileDialog
        $dialog.Title = 'Selecione o ZIP do robô SSW'
        $dialog.Filter = 'Arquivo ZIP (*.zip)|*.zip|Todos os arquivos (*.*)|*.*'
        $dialog.Multiselect = $false
        if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
            $SourcePath = $dialog.FileName
        }
    } catch {
        # Em ambientes sem WinForms, cai no prompt abaixo.
    }
}

if ([string]::IsNullOrWhiteSpace($SourcePath)) {
    $SourcePath = Read-Host 'Informe o caminho do ZIP ou da pasta do robô SSW'
}
$SourcePath = $SourcePath.Trim('"')
if (-not (Test-Path $SourcePath)) { throw "Fonte não encontrada: $SourcePath" }

$Temp = $null
$SourceRoot = $null
$item = Get-Item $SourcePath
if ($item.PSIsContainer) {
    $SourceRoot = $item.FullName
} elseif ($item.Extension -ieq '.zip') {
    $Temp = Join-Path $env:TEMP ("painel_robot_install_" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $Temp -Force | Out-Null
    Write-Step 'Extraindo ZIP do robô...'
    Expand-Archive -LiteralPath $item.FullName -DestinationPath $Temp -Force
    $SourceRoot = $Temp
} else {
    throw 'Selecione um arquivo .zip ou uma pasta do robô.'
}

# Se o ZIP tiver apenas uma pasta-raiz, usa o conteúdo dela.
$rootFiles = @(Get-ChildItem -LiteralPath $SourceRoot -File -Force)
$rootDirs = @(Get-ChildItem -LiteralPath $SourceRoot -Directory -Force)
if ($rootFiles.Count -eq 0 -and $rootDirs.Count -eq 1) {
    $SourceRoot = $rootDirs[0].FullName
}

New-Item -ItemType Directory -Path $RobotDir -Force | Out-Null
$BackupRoot = Join-Path $Root 'local_data\robot_backups'
New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$Backup = Join-Path $BackupRoot "before_p7_$stamp"
New-Item -ItemType Directory -Path $Backup -Force | Out-Null

Write-Step "Criando backup do robot_ssw em $Backup"
Get-ChildItem -LiteralPath $RobotDir -Force -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.Name -ne '__pycache__') {
        Copy-Item -LiteralPath $_.FullName -Destination $Backup -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$skipParts = @('.git', '.venv', 'venv', '__pycache__', 'node_modules', 'local_data')
$protectedNames = @('painel_adapter.py', 'credenciais.local.json')
$copied = 0
Write-Step 'Copiando arquivos do robô real...'
Get-ChildItem -LiteralPath $SourceRoot -Recurse -File -Force | ForEach-Object {
    $relative = $_.FullName.Substring($SourceRoot.Length).TrimStart('\','/')
    $parts = $relative -split '[\\/]'
    if (($parts | Where-Object { $skipParts -contains $_ }).Count -gt 0) { return }
    if ($protectedNames -contains $_.Name.ToLowerInvariant()) { return }
    if ($_.Extension -ieq '.pyc') { return }
    $dest = Join-Path $RobotDir $relative
    $destDir = Split-Path $dest -Parent
    New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    Copy-Item -LiteralPath $_.FullName -Destination $dest -Force
    $script:copied++
}

if ($copied -eq 0) { throw 'Nenhum arquivo foi copiado do pacote selecionado.' }
Write-Ok "$copied arquivo(s) copiado(s) para robot_ssw."

# Remove BOM antigo do .env.local para eliminar "Invalid line: ﻿DJANGO_DEBUG=1".
$EnvFile = Join-Path $Root '.env.local'
if (Test-Path $EnvFile) {
    $text = [System.IO.File]::ReadAllText($EnvFile)
    $text = $text.TrimStart([char]0xFEFF)
    [System.IO.File]::WriteAllText($EnvFile, $text, (New-Object System.Text.UTF8Encoding($false)))
    Write-Ok '.env.local normalizado para UTF-8 sem BOM.'
}

Write-Step 'Procurando automaticamente a função/entrypoint do robô...'
$adapter = Join-Path $RobotDir 'painel_adapter.py'
& $Python $adapter --discover-only
$discoverExit = $LASTEXITCODE

if ($discoverExit -eq 0) {
    Write-Ok 'Robô real detectado pelo adapter.'
    $cred = Join-Path $RobotDir 'credenciais.local.json'
    if (-not (Test-Path $cred)) {
        Write-Warn 'Credenciais ainda não configuradas. Execute CONFIGURAR_CREDENCIAIS_SSW.bat.'
    }
    Write-Host ''
    Write-Host 'Próximo passo: TESTAR_INTEGRACAO_ROBO_SSW.bat' -ForegroundColor White
} else {
    Write-Warn 'Os arquivos foram instalados, mas nenhuma função compatível foi encontrada automaticamente.'
    Write-Host 'Funções aceitas: executar_tarefa, buscar_relatorio, executar, run_task ou run.'
    Write-Host 'Arquivos Python encontrados:'
    Get-ChildItem -LiteralPath $RobotDir -Recurse -Filter '*.py' -File | Where-Object { $_.Name -ne 'painel_adapter.py' } | ForEach-Object {
        Write-Host ('  - ' + $_.FullName.Substring($RobotDir.Length + 1))
    }
    Write-Host ''
    Write-Host 'Nesse caso, envie essa lista/arquivo principal para ajustarmos o contrato.' -ForegroundColor Yellow
}

if ($Temp -and (Test-Path $Temp)) { Remove-Item -LiteralPath $Temp -Recurse -Force -ErrorAction SilentlyContinue }
