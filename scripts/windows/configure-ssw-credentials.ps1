$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$RobotDir = Join-Path $Root "robot_ssw"
$CredentialFile = Join-Path $RobotDir "credenciais.local.json"
New-Item -ItemType Directory -Force -Path $RobotDir | Out-Null

Write-Host "============================================================" -ForegroundColor Blue
Write-Host " PAINEL MOTORISTAS - CONFIGURAR CREDENCIAIS SSW (P11)" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Blue
Write-Host "Arquivo que sera gravado:" -ForegroundColor Gray
Write-Host "  $CredentialFile" -ForegroundColor Cyan
Write-Host ""

$ExistingDomain = ""
$ExistingCpf = ""
$ExistingUser = ""
$ExistingPassword = ""
$ExistingUrl = ""
if (Test-Path -LiteralPath $CredentialFile) {
    try {
        $current = Get-Content -LiteralPath $CredentialFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $ExistingDomain = [string]$current.domain
        if (-not $ExistingDomain) { $ExistingDomain = [string]$current.dominio }
        $ExistingCpf = ([string]$current.cpf) -replace '\D',''
        $ExistingUser = [string]$current.username
        if (-not $ExistingUser) { $ExistingUser = [string]$current.usuario }
        $ExistingPassword = [string]$current.password
        if (-not $ExistingPassword) { $ExistingPassword = [string]$current.senha }
        $ExistingUrl = [string]$current.login_url
        if (-not $ExistingUrl) { $ExistingUrl = [string]$current.url }
        Write-Host "Credencial anterior encontrada. Os campos existentes podem ser mantidos com Enter." -ForegroundColor Yellow
    } catch {
        Write-Host "Arquivo anterior existe, mas nao pode ser lido. Ele sera recriado." -ForegroundColor Yellow
    }
}

$domainPrompt = if ($ExistingDomain) { "Dominio SSW [$ExistingDomain] (Enter mantem)" } else { "Dominio SSW" }
$Domain = Read-Host $domainPrompt
if ([string]::IsNullOrWhiteSpace($Domain)) { $Domain = $ExistingDomain }
$Domain = $Domain.Trim()
if ([string]::IsNullOrWhiteSpace($Domain)) { throw "Dominio SSW nao informado." }

$cpfMasked = ""
if ($ExistingCpf) {
    if ($ExistingCpf.Length -ge 4) { $cpfMasked = ('*' * ($ExistingCpf.Length - 4)) + $ExistingCpf.Substring($ExistingCpf.Length - 4) }
    else { $cpfMasked = ('*' * $ExistingCpf.Length) }
}
$cpfPrompt = if ($ExistingCpf) { "CPF vinculado ao SSW [$cpfMasked] (Enter mantem)" } else { "CPF vinculado ao SSW" }
$Cpf = Read-Host $cpfPrompt
if ([string]::IsNullOrWhiteSpace($Cpf)) { $Cpf = $ExistingCpf }
$Cpf = $Cpf -replace '\D',''
if ([string]::IsNullOrWhiteSpace($Cpf)) { throw "CPF SSW nao informado." }

$userPrompt = if ($ExistingUser) { "Usuario SSW [$ExistingUser] (Enter mantem)" } else { "Usuario SSW" }
$Username = Read-Host $userPrompt
if ([string]::IsNullOrWhiteSpace($Username)) { $Username = $ExistingUser }
$Username = $Username.Trim()
if ([string]::IsNullOrWhiteSpace($Username)) { throw "Usuario SSW nao informado." }

if ($ExistingPassword) {
    $SecurePassword = Read-Host "Senha SSW (Enter mantem a senha atual)" -AsSecureString
} else {
    $SecurePassword = Read-Host "Senha SSW" -AsSecureString
}
$BSTR = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePassword)
try { $Password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($BSTR) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR) }
if ([string]::IsNullOrEmpty($Password)) { $Password = $ExistingPassword }
if ([string]::IsNullOrEmpty($Password)) { throw "Senha SSW nao informada." }

$urlPrompt = if ($ExistingUrl) { "URL de login do SSW [$ExistingUrl] (Enter mantem)" } else { "URL de login do SSW" }
$LoginUrl = Read-Host $urlPrompt
if ([string]::IsNullOrWhiteSpace($LoginUrl)) { $LoginUrl = $ExistingUrl }
$LoginUrl = $LoginUrl.Trim()
if ([string]::IsNullOrWhiteSpace($LoginUrl)) { throw "URL de login do SSW nao informada." }

$data = [ordered]@{
    schema_version = 2
    domain = $Domain
    cpf = $Cpf
    username = $Username
    password = $Password
    login_url = $LoginUrl
}
$json = $data | ConvertTo-Json
[System.IO.File]::WriteAllText($CredentialFile, $json, (New-Object System.Text.UTF8Encoding($false)))

# Leitura de volta: se gravou no lugar errado ou faltou uma chave, falha AGORA.
$check = Get-Content -LiteralPath $CredentialFile -Raw -Encoding UTF8 | ConvertFrom-Json
$missing = @()
if ([string]::IsNullOrWhiteSpace([string]$check.domain)) { $missing += "domain" }
if ([string]::IsNullOrWhiteSpace(([string]$check.cpf -replace '\D',''))) { $missing += "cpf" }
if ([string]::IsNullOrWhiteSpace([string]$check.username)) { $missing += "username" }
if ([string]::IsNullOrEmpty([string]$check.password)) { $missing += "password" }
if ([string]::IsNullOrWhiteSpace([string]$check.login_url)) { $missing += "login_url" }
if ($missing.Count -gt 0) { throw "Falha ao validar o arquivo salvo. Faltando: $($missing -join ', ')" }

Write-Host ""
Write-Host "CREDENCIAIS SALVAS E VALIDADAS." -ForegroundColor Green
Write-Host "Arquivo : $CredentialFile" -ForegroundColor Cyan
Write-Host "Dominio : SIM" -ForegroundColor Green
Write-Host "CPF     : SIM ($($check.cpf.ToString().Length) digitos)" -ForegroundColor Green
Write-Host "Usuario : SIM" -ForegroundColor Green
Write-Host "Senha   : SIM" -ForegroundColor Green
Write-Host "URL     : SIM" -ForegroundColor Green
Write-Host ""
Write-Host "Agora execute VERIFICAR_CREDENCIAIS_SSW.bat e depois TESTAR_LOGIN_ROBO_SSW.bat." -ForegroundColor Yellow
