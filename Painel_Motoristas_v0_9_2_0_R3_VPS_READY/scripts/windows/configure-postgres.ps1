$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common-native.ps1")
$Root = Get-Root
Set-Location $Root

Write-Host "CONFIGURAR POSTGRESQL LOCAL - SEM DOCKER" -ForegroundColor Cyan
Write-Host "Use isto somente se o PostgreSQL ja estiver instalado e o banco/usuario existirem." -ForegroundColor Gray
Write-Host "Para rodar imediatamente sem instalar PostgreSQL, mantenha o modo SQLite do EXECUTAR_LOCAL.bat.`n" -ForegroundColor Gray

$hostName = Read-Host "Host [localhost]"
if (-not $hostName) { $hostName = "localhost" }
$port = Read-Host "Porta [5432]"
if (-not $port) { $port = "5432" }
$dbName = Read-Host "Banco [painel_motoristas]"
if (-not $dbName) { $dbName = "painel_motoristas" }
$dbUser = Read-Host "Usuario [painel]"
if (-not $dbUser) { $dbUser = "painel" }
$secure = Read-Host "Senha do usuario PostgreSQL" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try { $dbPass = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
if (-not $dbPass) { Fail "A senha nao pode ficar vazia." }

$secret = ([guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N"))
$escapedUser = [uri]::EscapeDataString($dbUser)
$escapedPass = [uri]::EscapeDataString($dbPass)
$envText = @"
DJANGO_DEBUG=1
DJANGO_SECRET_KEY=$secret
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_MODE=postgres
DATABASE_URL=postgresql://${escapedUser}:${escapedPass}@${hostName}:${port}/${dbName}
CELERY_TASK_ALWAYS_EAGER=1
TZ=America/Belem
LOCAL_ADMIN_USERNAME=admin
LOCAL_ADMIN_PASSWORD=Painel@2026!
LOCAL_ADMIN_EMAIL=admin@localhost
SSW_USERNAME=
SSW_PASSWORD=
"@
[System.IO.File]::WriteAllText((Join-Path $Root ".env.local"), $envText, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "`nConfiguracao salva. Execute EXECUTAR_LOCAL.bat para testar a conexao e aplicar migrations." -ForegroundColor Green
Read-Host "Pressione ENTER para fechar"
