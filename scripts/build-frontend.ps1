param(
    [string]$FrontendDir = (Join-Path $PSScriptRoot "..\frontend")
)

$ErrorActionPreference = "Stop"

$frontendPath = Resolve-Path $FrontendDir
Push-Location $frontendPath
try {
    $distPath = Join-Path $frontendPath "dist"
    if (Test-Path $distPath) {
        Write-Host "[frontend] Removing previous dist output..."
        Remove-Item -LiteralPath $distPath -Recurse -Force
    }

    Write-Host "[frontend] Building Vue production bundle..."
    & ".\node_modules\.bin\vue-tsc.cmd" -b
    if ($LASTEXITCODE -ne 0) {
        throw "vue-tsc failed with exit code $LASTEXITCODE"
    }

    & ".\node_modules\.bin\vite.cmd" build --configLoader runner
    if ($LASTEXITCODE -ne 0) {
        throw "vite build failed with exit code $LASTEXITCODE"
    }

    Write-Host "[frontend] Build complete: $frontendPath\dist"
}
finally {
    Pop-Location
}
