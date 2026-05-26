param(
    [switch]$SkipBackendTests,
    [switch]$SkipFrontendBuild,
    [switch]$CheckRunningServices
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

Set-Location $RepoRoot

Write-Step "Git status"
git status --short --branch

if (-not $SkipBackendTests) {
    Write-Step "Backend tests"
    powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "run-backend-tests.ps1")
}

if (-not $SkipFrontendBuild) {
    Write-Step "Frontend production build"
    Push-Location (Join-Path $RepoRoot "frontend")
    try {
        npm.cmd run build
    }
    finally {
        Pop-Location
    }
}

if ($CheckRunningServices) {
    Write-Step "Running service health checks"
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 5
    if (-not $health.success -or $health.data.status -ne "ok") {
        throw "Backend health check failed."
    }
    Write-Host "Backend health check passed." -ForegroundColor Green

    $frontend = Invoke-WebRequest -Uri "http://127.0.0.1:5173" -UseBasicParsing -TimeoutSec 5
    if ($frontend.StatusCode -lt 200 -or $frontend.StatusCode -ge 400) {
        throw "Frontend page check failed with status $($frontend.StatusCode)."
    }
    Write-Host "Frontend page check passed." -ForegroundColor Green
}

Write-Step "Verification completed"
Write-Host "Local verification finished. Review warnings above before packaging or recording." -ForegroundColor Green
