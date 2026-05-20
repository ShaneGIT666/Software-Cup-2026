param(
    [int]$Port = 8000,
    [string]$EnvName = "software-cup-2026"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $RepoRoot "backend"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    & $PSScriptRoot\setup-anaconda.ps1 -EnvName $EnvName
}

& $VenvPython -m uvicorn app.main:app --reload --host 127.0.0.1 --port $Port --app-dir $BackendDir
