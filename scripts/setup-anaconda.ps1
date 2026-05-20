param(
    [string]$EnvName = "software-cup-2026"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $RepoRoot "backend"
$VenvDir = Join-Path $BackendDir ".venv"
$PythonCandidates = @(
    "C:\Users\liuzi\anaconda3\python.exe",
    "C:\Users\liuzi\.anaconda\python.exe"
)

function Get-AnacondaPython {
    foreach ($candidate in $PythonCandidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw "Anaconda Python was not found. Install Anaconda or Miniconda first."
}

$PythonExe = Get-AnacondaPython

if (-not (Test-Path (Join-Path $VenvDir "Scripts\python.exe"))) {
    & $PythonExe -m venv $VenvDir
}

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $BackendDir "requirements.txt")
