$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $RepoRoot "backend"
$EnvName = "software-cup-2026"
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    & $PSScriptRoot\setup-anaconda.ps1 -EnvName $EnvName
}

& $PythonExe -m pytest (Join-Path $RepoRoot "tests")
