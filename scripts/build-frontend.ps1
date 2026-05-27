param(
    [string]$FrontendDir = (Join-Path $PSScriptRoot "..\frontend")
)

$ErrorActionPreference = "Stop"

$frontendPath = Resolve-Path $FrontendDir
Push-Location $frontendPath
try {
    Write-Host "[frontend] Building Vue production bundle..."
    npm.cmd run build
    Write-Host "[frontend] Build complete: $frontendPath\dist"
}
finally {
    Pop-Location
}
