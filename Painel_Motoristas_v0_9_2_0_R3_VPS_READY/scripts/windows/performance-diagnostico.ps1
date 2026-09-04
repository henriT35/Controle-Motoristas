$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Log = Join-Path $Root "local_data\logs\painel.log"

Write-Host "===============================================" -ForegroundColor Blue
Write-Host " PAINEL MOTORISTAS - DIAGNOSTICO PERFORMANCE" -ForegroundColor White
Write-Host "===============================================" -ForegroundColor Blue

if (-not (Test-Path $Log)) {
    Write-Host "Ainda nao existe local_data\logs\painel.log." -ForegroundColor Yellow
    Write-Host "Abra algumas telas do Painel e execute este arquivo novamente."
    Read-Host "Pressione ENTER para fechar"
    exit 0
}

$allPerf = @(Get-Content $Log -Tail 12000 | Where-Object { $_ -match 'PERF ' })
if ($allPerf.Count -eq 0) {
    Write-Host "Nenhuma medicao PERF encontrada ainda." -ForegroundColor Yellow
    Read-Host "Pressione ENTER para fechar"
    exit 0
}

# A R3 grava PERF session.start ao iniciar LOCAL/ONLINE. Se o pacote foi iniciado
# por uma build anterior, usamos o ultimo warmup como corte seguro. Isso evita
# que o TOP 20 misture tempos de versões/sessoes antigas com o teste atual.
$startIndex = -1
$marker = $null
for ($i = $allPerf.Count - 1; $i -ge 0; $i--) {
    if ($allPerf[$i] -match 'PERF session\.start') {
        $startIndex = $i
        $marker = $allPerf[$i]
        break
    }
}
if ($startIndex -lt 0) {
    for ($i = $allPerf.Count - 1; $i -ge 0; $i--) {
        if ($allPerf[$i] -match 'PERF warmup\.done') {
            $startIndex = $i
            $marker = $allPerf[$i]
            break
        }
    }
}

$lines = if ($startIndex -ge 0) { @($allPerf[$startIndex..($allPerf.Count-1)]) } else { $allPerf }

function Convert-PerfRows($sourceLines) {
    $items = @()
    foreach ($line in $sourceLines) {
        if ($line -match 'PERF ([A-Za-z0-9_.-]+)\.total = ([0-9.]+)s') {
            $items += [pscustomobject]@{
                Tela=$matches[1]
                Segundos=[double]$matches[2]
                Linha=$line
            }
        }
    }
    return @($items)
}

$rows = Convert-PerfRows $lines
$historicalRows = Convert-PerfRows $allPerf

Write-Host "`n==> Sessao analisada" -ForegroundColor Cyan
if ($marker) {
    Write-Host $marker -ForegroundColor Gray
} else {
    Write-Host "Sem marcador de sessao; usando as ultimas linhas disponiveis." -ForegroundColor Yellow
}
Write-Host "Linhas PERF nesta sessao: $($lines.Count)"

Write-Host "`n==> 20 requests/etapas mais lentas DESTA SESSAO" -ForegroundColor Cyan
if ($rows.Count -eq 0) {
    Write-Host "Nenhum .total encontrado nesta sessao ainda." -ForegroundColor Yellow
} else {
    $rows | Sort-Object Segundos -Descending | Select-Object -First 20 Tela,Segundos | Format-Table -AutoSize
}

Write-Host "`n==> Resumo por tela DESTA SESSAO" -ForegroundColor Cyan
$requestScreens = @('dashboard.request','dashboard','ranking','drivers','deliveries','operation.today','proofs','quality.reviews','portal','whatsapp','dashboard.graph')
$summary = @()
foreach ($screen in $requestScreens) {
    $set = @($rows | Where-Object { $_.Tela -eq $screen })
    if ($set.Count -gt 0) {
        $avg = ($set | Measure-Object -Property Segundos -Average).Average
        $max = ($set | Measure-Object -Property Segundos -Maximum).Maximum
        $last = $set[-1].Segundos
        $summary += [pscustomobject]@{
            Tela=$screen
            Amostras=$set.Count
            Ultima=[math]::Round($last,3)
            Media=[math]::Round($avg,3)
            Max=[math]::Round($max,3)
        }
    }
}
if ($summary.Count -gt 0) {
    $summary | Sort-Object Max -Descending | Format-Table -AutoSize
} else {
    Write-Host "Ainda nao ha requests das telas criticas nesta sessao." -ForegroundColor Yellow
}

Write-Host "`n==> Ranking: cache/snapshot DESTA SESSAO" -ForegroundColor Cyan
$snapshotHits = @($lines | Where-Object { $_ -match 'PERF ranking\.snapshot_hit' }).Count
$cacheHits = @($lines | Where-Object { $_ -match 'PERF ranking\.cache_hit' }).Count
$rankingSlow = @($rows | Where-Object { $_.Tela -eq 'ranking' -and $_.Segundos -ge 2 }).Count
Write-Host "Snapshot hits : $snapshotHits"
Write-Host "Cache hits    : $cacheHits"
Write-Host "Ranking >=2s  : $rankingSlow"
if ($snapshotHits -gt 0) {
    Write-Host "OK: houve cache miss atendido por snapshot persistente." -ForegroundColor Green
}
if ($rankingSlow -eq 0 -and (@($rows | Where-Object { $_.Tela -eq 'ranking' }).Count -gt 0)) {
    Write-Host "OK: nenhum ranking >=2s nesta sessao." -ForegroundColor Green
}

Write-Host "`n==> SQL das telas criticas DESTA SESSAO (ultimas 30)" -ForegroundColor Cyan
$lines | Where-Object { $_ -match 'PERF .*\.sql queries=' } | Select-Object -Last 30

Write-Host "`n==> Ultimas etapas internas DESTA SESSAO" -ForegroundColor Cyan
$lines | Select-Object -Last 70

# Mantemos apenas um alerta historico curto. Ele nao participa mais do ranking
# principal e serve para lembrar que o arquivo pode conter medicoes de builds antigas.
$oldSlow = @($historicalRows | Where-Object { $_.Segundos -ge 10 }).Count
if ($oldSlow -gt 0) {
    Write-Host "`nHistorico: existem $oldSlow medicoes >=10s no arquivo completo (podem ser de builds/sessoes anteriores)." -ForegroundColor DarkGray
}

Write-Host "`nLog completo: $Log" -ForegroundColor Gray
Read-Host "Pressione ENTER para fechar"
