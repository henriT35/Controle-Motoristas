$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$node = Join-Path $Root "tools\node\node.exe"
if (-not (Test-Path $node)) {
    $cmd = Get-Command node.exe -ErrorAction SilentlyContinue
    if ($cmd) { $node = $cmd.Source }
}
if (-not $node -or -not (Test-Path $node)) { throw "Node.js nao encontrado. Rode INSTALAR_BOT_WHATSAPP.bat." }
$bridge = Join-Path $Root "whatsapp_bridge"
if (-not (Test-Path (Join-Path $bridge "node_modules\@whiskeysockets\baileys\package.json"))) {
    throw "Baileys nao instalado. Rode INSTALAR_BOT_WHATSAPP.bat."
}
$env:PANEL_BASE_DIR = $Root
$env:PANEL_INTERNAL_URL = "http://127.0.0.1:8000"
Set-Location $bridge
& $node (Join-Path $bridge "server.mjs")
