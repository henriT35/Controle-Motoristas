$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $Root

Write-Host "===============================================" -ForegroundColor Blue
Write-Host " WHATSAPP - BAILEYS / NODE.JS" -ForegroundColor White
Write-Host " Instalacao sem Chrome, Edge ou Playwright" -ForegroundColor Gray
Write-Host "===============================================" -ForegroundColor Blue

$MinNodeMajor = 20
$PortableVersion = "24.20.0"
$NodeExe = $null
$NpmCmd = $null

function Test-Node20([string]$Candidate) {
    if (-not $Candidate -or -not (Test-Path $Candidate)) { return $false }
    try {
        $v = & $Candidate -p "process.versions.node" 2>$null
        $major = [int](($v -split '\.')[0])
        return $major -ge $MinNodeMajor
    } catch { return $false }
}

function Stop-WhatsappBridgeNode {
    # Fecha somente processos Node do bridge deste projeto. Nao mata outros Node do computador.
    try {
        Get-CimInstance Win32_Process -Filter "Name = 'node.exe'" -ErrorAction SilentlyContinue |
            Where-Object {
                $_.CommandLine -and
                $_.CommandLine -like "*$Root*" -and
                $_.CommandLine -match "whatsapp_bridge.*server\.mjs"
            } |
            ForEach-Object {
                Write-Host "==> Encerrando bridge WhatsApp anterior (PID $($_.ProcessId))..." -ForegroundColor DarkYellow
                Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            }
        Start-Sleep -Milliseconds 500
    } catch {
        Write-Host "Aviso: nao foi possivel consultar processos Node anteriores: $($_.Exception.Message)" -ForegroundColor DarkYellow
    }
}

function Remove-PartialNodeModules([string]$Bridge) {
    $modules = Join-Path $Bridge "node_modules"
    if (-not (Test-Path $modules)) { return }

    Write-Host "==> Limpando instalacao Node incompleta anterior..." -ForegroundColor Cyan
    Stop-WhatsappBridgeNode

    # Remove-Item pode falhar temporariamente no Windows por antivirus/indexacao.
    # Faz tentativas curtas antes de desistir com uma mensagem clara.
    $lastError = $null
    for ($i = 1; $i -le 4; $i++) {
        try {
            Remove-Item $modules -Recurse -Force -ErrorAction Stop
            return
        } catch {
            $lastError = $_
            Start-Sleep -Milliseconds (500 * $i)
        }
    }

    # Fallback do proprio Windows para arvores grandes de node_modules.
    try {
        cmd.exe /d /c "rmdir /s /q `"$modules`"" | Out-Null
        Start-Sleep -Milliseconds 500
        if (-not (Test-Path $modules)) { return }
    } catch {
        $lastError = $_
    }

    throw "Nao foi possivel limpar whatsapp_bridge\node_modules. Feche o Painel/bot e tente novamente. Detalhe: $($lastError.Exception.Message)"
}

$portableNode = Join-Path $Root "tools\node\node.exe"
if (Test-Node20 $portableNode) {
    $NodeExe = $portableNode
    $NpmCmd = Join-Path $Root "tools\node\npm.cmd"
} else {
    $systemNode = Get-Command node.exe -ErrorAction SilentlyContinue
    if ($systemNode -and (Test-Node20 $systemNode.Source)) {
        $NodeExe = $systemNode.Source
        $systemNpm = Get-Command npm.cmd -ErrorAction SilentlyContinue
        if ($systemNpm) { $NpmCmd = $systemNpm.Source }
    }
}

if (-not $NodeExe -or -not $NpmCmd) {
    Write-Host "`n==> Node.js 20+ nao encontrado. Baixando Node.js $PortableVersion LTS oficial..." -ForegroundColor Cyan
    $tools = Join-Path $Root "tools\node"
    $tmp = Join-Path $env:TEMP "painel-node-$PortableVersion.zip"
    $stage = Join-Path $env:TEMP "painel-node-$PortableVersion"
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $stage | Out-Null
    $url = "https://nodejs.org/dist/v$PortableVersion/node-v$PortableVersion-win-x64.zip"
    Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing
    Expand-Archive -Path $tmp -DestinationPath $stage -Force
    $source = Join-Path $stage "node-v$PortableVersion-win-x64"
    if (-not (Test-Path (Join-Path $source "node.exe"))) { throw "Pacote Node.js baixado nao possui node.exe." }
    Remove-Item $tools -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $tools | Out-Null
    Copy-Item (Join-Path $source "*") $tools -Recurse -Force
    $NodeExe = Join-Path $tools "node.exe"
    $NpmCmd = Join-Path $tools "npm.cmd"
}

if (-not (Test-Node20 $NodeExe)) { throw "Node.js 20+ nao ficou disponivel." }
if (-not (Test-Path $NpmCmd)) { throw "npm.cmd nao ficou disponivel junto do Node.js." }

# CORRECAO v0.7.1.1:
# npm consegue ser chamado pelo caminho absoluto, mas scripts lifecycle de dependencias
# executam `node ...` pelo shell. O Node portatil precisa estar no PATH deste processo
# e de todos os subprocessos criados pelo npm.
$NodeDir = Split-Path -Parent $NodeExe
$pathParts = @($env:Path -split ';' | Where-Object { $_ })
if (-not ($pathParts | Where-Object { $_.TrimEnd('\') -ieq $NodeDir.TrimEnd('\') })) {
    $env:Path = "$NodeDir;$env:Path"
}
$env:NODE = $NodeExe
$env:npm_node_execpath = $NodeExe

Write-Host "Node: $(& $NodeExe -v)" -ForegroundColor Green
Write-Host "npm : $(& $NpmCmd -v)" -ForegroundColor Green

# Prova antes do npm install que um subprocesso comum realmente encontra `node`.
$nodeOnPath = Get-Command node.exe -ErrorAction SilentlyContinue
if (-not $nodeOnPath) { throw "Node existe, mas nao ficou disponivel no PATH do instalador." }
$pathVersion = & node.exe -v
if ($LASTEXITCODE -ne 0) { throw "Falha ao executar node.exe pelo PATH." }
Write-Host "PATH: node.exe disponivel ($pathVersion)" -ForegroundColor Green

$Bridge = Join-Path $Root "whatsapp_bridge"
if (-not (Test-Path (Join-Path $Bridge "package.json"))) { throw "whatsapp_bridge\package.json nao encontrado." }

$baileysPkg = Join-Path $Bridge "node_modules\@whiskeysockets\baileys\package.json"
$pinoPkg = Join-Path $Bridge "node_modules\pino\package.json"
$qrcodePkg = Join-Path $Bridge "node_modules\qrcode\package.json"
$depsReady = (Test-Path $baileysPkg) -and (Test-Path $pinoPkg) -and (Test-Path $qrcodePkg)

if ($depsReady) {
    Write-Host "`n==> Baileys ja esta instalado. Validando..." -ForegroundColor Cyan
} else {
    Remove-PartialNodeModules $Bridge
    $partialLock = Join-Path $Bridge "package-lock.json"
    if (Test-Path $partialLock) {
        Remove-Item $partialLock -Force -ErrorAction SilentlyContinue
    }

    Write-Host "`n==> Instalando Baileys e gerador de QR" -ForegroundColor Cyan
    Push-Location $Bridge
    try {
        & $NpmCmd install --omit=dev --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw "npm install retornou codigo $LASTEXITCODE" }
    } finally {
        Pop-Location
    }
}

if (-not ((Test-Path $baileysPkg) -and (Test-Path $pinoPkg) -and (Test-Path $qrcodePkg))) {
    throw "npm terminou, mas as dependencias obrigatorias do bridge nao foram encontradas em node_modules."
}

& $NodeExe --check (Join-Path $Bridge "server.mjs")
if ($LASTEXITCODE -ne 0) { throw "server.mjs possui erro de sintaxe" }

Write-Host "`nINSTALACAO CONCLUIDA." -ForegroundColor Green
Write-Host "Agora abra WhatsApp Motoristas > Conectar / QR Code e clique em Gerar QR Code." -ForegroundColor White
