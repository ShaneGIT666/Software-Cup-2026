param(
    [int]$Port = 5173
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$FrontendDir = Join-Path $RepoRoot "frontend"
$NpmCache = Join-Path $RepoRoot ".npm-cache"

Push-Location $FrontendDir
try {
    if (-not (Test-Path "node_modules")) {
        npm.cmd install --cache $NpmCache
    }
    $ErrorActionPreference = "Continue"
    npm.cmd run dev -- --host 127.0.0.1 --port $Port
}
finally {
    Pop-Location
}
