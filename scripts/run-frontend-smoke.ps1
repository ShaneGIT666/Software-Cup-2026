param(
    [string]$BaseUrl = "http://127.0.0.1:5173"
)

$ErrorActionPreference = "Stop"
$frontendDir = Resolve-Path (Join-Path $PSScriptRoot "..\frontend")

Push-Location $frontendDir
try {
    $env:E2E_BASE_URL = $BaseUrl
    npm.cmd run test:e2e
}
finally {
    Pop-Location
}
