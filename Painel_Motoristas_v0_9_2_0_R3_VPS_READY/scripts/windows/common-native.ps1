function Get-Root {
    return (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

function Find-Python {
    $candidates = @(
        @{Cmd="py"; Args=@("-3.12")},
        @{Cmd="py"; Args=@("-3")},
        @{Cmd="python"; Args=@()}
    )
    foreach ($c in $candidates) {
        if (Get-Command $c.Cmd -ErrorAction SilentlyContinue) {
            try {
                & $c.Cmd @($c.Args) -c "import sys; assert sys.version_info >= (3,10)" 2>$null
                if ($LASTEXITCODE -eq 0) { return $c }
            } catch {}
        }
    }
    return $null
}

function Fail([string]$Text) {
    Write-Host "`nERRO: $Text" -ForegroundColor Red
    Write-Host "`nPressione ENTER para fechar..." -ForegroundColor DarkGray
    [void](Read-Host)
    exit 1
}

function Ensure-Venv([string]$Root) {
    $py = Find-Python
    if (-not $py) {
        Fail "Python 3.10+ nao foi encontrado. Execute INSTALAR_PYTHON.bat e depois tente novamente."
    }
    $venvPython = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        Write-Host "`n==> Criando ambiente virtual Python" -ForegroundColor Cyan
        & $py.Cmd @($py.Args) -m venv (Join-Path $Root ".venv")
        if ($LASTEXITCODE -ne 0) { Fail "Nao foi possivel criar o ambiente virtual." }
    }
    return $venvPython
}

function Ensure-EnvFile([string]$Root) {
    $envPath = Join-Path $Root ".env.local"
    if (-not (Test-Path $envPath)) {
        $secret = ([guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N"))
        $text = @"
DJANGO_DEBUG=1
DJANGO_SECRET_KEY=$secret
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_MODE=sqlite
SQLITE_PATH=local_data/painel_motoristas.sqlite3
CELERY_TASK_ALWAYS_EAGER=1
TZ=America/Belem
LOCAL_ADMIN_USERNAME=admin
LOCAL_ADMIN_PASSWORD=Painel@2026!
LOCAL_ADMIN_EMAIL=admin@localhost
SSW_USERNAME=
SSW_PASSWORD=
SSW_IMPORT_ENGINE=v2
"@
        [System.IO.File]::WriteAllText($envPath, $text, (New-Object System.Text.UTF8Encoding($false)))
    }
}


function Ensure-LocalDependencies([string]$Root, [string]$Python) {
    $requirements = Join-Path $Root "requirements-local.txt"
    $dataDir = Join-Path $Root "local_data"
    New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
    $stamp = Join-Path $dataDir "requirements-local.sha256"
    $currentHash = (Get-FileHash -Algorithm SHA256 -Path $requirements).Hash

    $needsInstall = $true
    if (Test-Path $stamp) {
        $savedHash = (Get-Content $stamp -ErrorAction SilentlyContinue | Select-Object -First 1)
        if ($savedHash -eq $currentHash) {
            & $Python -c "import django, celery, redis, environ, whitenoise, openpyxl, reportlab, waitress" 2>$null
            if ($LASTEXITCODE -eq 0) { $needsInstall = $false }
        }
    }

    if (-not $needsInstall) {
        Write-Host "==> Dependencias Python ja estao prontas." -ForegroundColor DarkGray
        return
    }

    Write-Host "==> Preparando pip" -ForegroundColor Cyan
    & $Python -m pip --version *> $null
    if ($LASTEXITCODE -ne 0) {
        & $Python -m ensurepip --upgrade
        if ($LASTEXITCODE -ne 0) { Fail "Nao foi possivel preparar o pip no ambiente virtual." }
    }

    # Atualizar pip ajuda em instalações novas, mas não deve bloquear o sistema se
    # a internet estiver lenta/indisponível e o pip atual já funcionar.
    & $Python -m pip install --disable-pip-version-check -q --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Aviso: nao foi possivel atualizar o pip. Continuando com a versao atual." -ForegroundColor Yellow
    }

    Write-Host "==> Instalando dependencias do Painel Motoristas" -ForegroundColor Cyan
    & $Python -m pip install --disable-pip-version-check --prefer-binary -q -r $requirements
    if ($LASTEXITCODE -ne 0) { Fail "Falha ao instalar dependencias Python. Verifique sua internet e tente novamente." }

    Set-Content -Path $stamp -Value $currentHash -Encoding ASCII
}
