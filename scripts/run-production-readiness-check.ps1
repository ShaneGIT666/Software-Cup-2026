param()

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$PythonExe = Join-Path $RepoRoot "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}

Set-Location $RepoRoot
Write-Warning "Legacy prototype offline smoke only: this does not call /api/v1/health/ready or verify PostgreSQL, authentication, proxy, or production deployment."
& $PythonExe (Join-Path $PSScriptRoot "production_readiness_check.py")
