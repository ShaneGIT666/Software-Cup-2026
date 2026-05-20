param(
    [int[]]$Ports = @(8000, 5173)
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$RuntimeDir = Join-Path $RepoRoot ".dev-runtime"
$PidFile = Join-Path $RuntimeDir "dev-processes.json"

function Stop-ProcessTreeById {
    param([int]$ProcessId)

    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped process $ProcessId"
    }
}

if (Test-Path $PidFile) {
    $runtime = Get-Content $PidFile -Raw | ConvertFrom-Json
    foreach ($entry in @($runtime.backend, $runtime.frontend)) {
        if ($entry.pid) {
            Stop-ProcessTreeById -ProcessId ([int]$entry.pid)
        }
    }
}

foreach ($port in $Ports) {
    $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
        if ($connection.OwningProcess) {
            Stop-ProcessTreeById -ProcessId ([int]$connection.OwningProcess)
        }
    }
}

if (Test-Path $PidFile) {
    Remove-Item -LiteralPath $PidFile -Force
}

Write-Host "Development servers stopped."
