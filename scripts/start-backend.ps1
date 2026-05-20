param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $RepoRoot "backend"
$VenvDir = Join-Path $BackendDir ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$CodexPython = Join-Path $HOME ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

function Get-BasePython {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($PythonCommand) {
        return $PythonCommand.Source
    }

    $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($PyLauncher) {
        $PreviousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $PyLauncher.Source -3 --version *> $null
        $PyExitCode = $LASTEXITCODE
        $ErrorActionPreference = $PreviousErrorActionPreference
        if ($PyExitCode -eq 0) {
            return "py -3"
        }
    }

    if (Test-Path $CodexPython) {
        return $CodexPython
    }

    throw "Python 3 was not found. Install Python 3.10+ or configure a local runtime."
}

if (-not (Test-Path $PythonExe)) {
    $BasePython = Get-BasePython
    if ($BasePython -eq "py -3") {
        py -3 -m venv $VenvDir
    }
    else {
        & $BasePython -m venv $VenvDir
    }
}

& $PythonExe -m pip install -r (Join-Path $BackendDir "requirements.txt")
& $PythonExe -m uvicorn app.main:app --reload --host 127.0.0.1 --port $Port --app-dir $BackendDir
