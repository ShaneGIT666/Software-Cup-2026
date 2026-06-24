param(
    [switch]$Repair
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$PythonExe = Join-Path $RepoRoot "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}

$Arguments = @((Join-Path $PSScriptRoot "json_store_maintenance.py"), "--root", $RepoRoot)
if ($Repair) {
    $Arguments += "--repair"
}

Set-Location $RepoRoot
& $PythonExe @Arguments
