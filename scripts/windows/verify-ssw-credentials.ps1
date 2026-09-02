$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$CredentialFile = Join-Path $Root "robot_ssw\credenciais.local.json"
Write-Host "============================================================" -ForegroundColor Blue
Write-Host " VERIFICACAO DAS CREDENCIAIS SSW" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Blue
Write-Host "Arquivo esperado:" -ForegroundColor Gray
Write-Host "  $CredentialFile" -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath $CredentialFile)) {
    Write-Host "Existe    : NAO" -ForegroundColor Red
    exit 2
}
Write-Host "Existe    : SIM" -ForegroundColor Green
try { $c = Get-Content -LiteralPath $CredentialFile -Raw -Encoding UTF8 | ConvertFrom-Json }
catch { Write-Host "JSON valido: NAO - $($_.Exception.Message)" -ForegroundColor Red; exit 3 }
Write-Host "JSON valido: SIM" -ForegroundColor Green
$domain = [string]$c.domain; if (-not $domain) { $domain=[string]$c.dominio }
$cpf = ([string]$c.cpf) -replace '\D',''
$user = [string]$c.username; if (-not $user) { $user=[string]$c.usuario }
$pass = [string]$c.password; if (-not $pass) { $pass=[string]$c.senha }
$url = [string]$c.login_url; if (-not $url) { $url=[string]$c.url }
Write-Host ("domain    : " + $(if($domain){"SIM"}else{"NAO"})) -ForegroundColor $(if($domain){"Green"}else{"Red"})
Write-Host ("cpf       : " + $(if($cpf){"SIM ($($cpf.Length) digitos)"}else{"NAO"})) -ForegroundColor $(if($cpf){"Green"}else{"Red"})
Write-Host ("username  : " + $(if($user){"SIM"}else{"NAO"})) -ForegroundColor $(if($user){"Green"}else{"Red"})
Write-Host ("password  : " + $(if($pass){"SIM"}else{"NAO"})) -ForegroundColor $(if($pass){"Green"}else{"Red"})
Write-Host ("login_url : " + $(if($url){"SIM"}else{"NAO"})) -ForegroundColor $(if($url){"Green"}else{"Red"})
$keys = @($c.psobject.Properties.Name | Sort-Object)
Write-Host "Chaves no JSON: $($keys -join ', ')" -ForegroundColor Gray
if (-not $domain -or -not $cpf -or -not $user -or -not $pass -or -not $url) { exit 4 }
Write-Host ""
Write-Host "RESULTADO: CREDENCIAIS COMPLETAS." -ForegroundColor Green
