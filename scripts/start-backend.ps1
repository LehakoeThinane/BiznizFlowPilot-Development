Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Set-Location (Join-Path $PSScriptRoot '..')

$repoRoot = (Get-Location).Path
if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $env:PYTHONPATH = $repoRoot
} else {
    $env:PYTHONPATH = $repoRoot + [IO.Path]::PathSeparator + $env:PYTHONPATH
}

function Test-PythonModule {
    param(
        [Parameter(Mandatory = $true)]
        [string] $PythonExe,

        [Parameter(Mandatory = $true)]
        [string] $ModuleName
    )

    & $PythonExe -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('$ModuleName') else 1)" *> $null
    return ($LASTEXITCODE -eq 0)
}

function Ensure-Dependencies {
    param(
        [Parameter(Mandatory = $true)]
        [string] $PythonExe
    )

    if ((Test-PythonModule -PythonExe $PythonExe -ModuleName 'alembic') -and (Test-PythonModule -PythonExe $PythonExe -ModuleName 'uvicorn')) {
        return
    }

    & $PythonExe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install backend dependencies with '$PythonExe'."
    }
    if (-not ((Test-PythonModule -PythonExe $PythonExe -ModuleName 'alembic') -and (Test-PythonModule -PythonExe $PythonExe -ModuleName 'uvicorn'))) {
        throw "Python at '$PythonExe' still does not have the required backend dependencies after installing requirements.txt."
    }
}

$pythonCandidates = @(
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
    (Join-Path (Get-Location) '.venv\Scripts\python.exe'),
    (Join-Path (Get-Location) 'venv312\Scripts\python.exe'),
    (Join-Path (Get-Location) 'venv\Scripts\python.exe')
)

$pythonExe = $null
foreach ($candidate in $pythonCandidates) {
    if (Test-Path $candidate) {
        $pythonExe = $candidate
        break
    }
}

if (-not $pythonExe) {
    throw 'No Python interpreter found. Install Python 3.12 or create a virtual environment before starting the backend.'
}

Ensure-Dependencies -PythonExe $pythonExe

if (-not $env:DATABASE_URL) {
    $preferDockerPort = $false
    try {
        $preferDockerPort = Test-NetConnection -ComputerName '127.0.0.1' -Port 5433 -InformationLevel Quiet -WarningAction SilentlyContinue
    } catch {
        $preferDockerPort = $false
    }

    if ($preferDockerPort) {
        $env:DATABASE_URL = 'postgresql://postgres:020890@localhost:5433/biznizflow_test'
    } else {
        $env:DATABASE_URL = 'postgresql://postgres:020890@localhost:5432/biznizflow_test'
    }
}

& $pythonExe -m alembic -c migrations\alembic.ini upgrade head
if ($LASTEXITCODE -ne 0) {
    throw 'Alembic migration failed.'
}
& $pythonExe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app
