param([Parameter(Mandatory=$true)][ValidateSet('1','0')][string]$Enabled)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common-native.ps1')
$Root = Get-Root
$EnvFile = Join-Path $Root '.env.local'
Ensure-EnvFile $Root
$content = Get-Content $EnvFile -Raw
if ($content -match '(?m)^SSW_ROBOT_ENABLED=') {
  $content = [regex]::Replace($content, '(?m)^SSW_ROBOT_ENABLED=.*$', "SSW_ROBOT_ENABLED=$Enabled")
} else {
  if ($content -and -not $content.EndsWith("`n")) { $content += "`r`n" }
  $content += "SSW_ROBOT_ENABLED=$Enabled`r`n"
}
Set-Content -Path $EnvFile -Value $content -Encoding UTF8
if ($Enabled -eq '1') {
  Write-Host 'Robô SSW habilitado no Painel.' -ForegroundColor Green
  Write-Host 'As credenciais continuam configuradas no próprio robô.' -ForegroundColor Gray
} else {
  Write-Host 'Robô SSW desabilitado no Painel.' -ForegroundColor Yellow
}
