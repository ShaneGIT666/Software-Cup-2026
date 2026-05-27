param(
    [string]$OutputDir = (Join-Path $PSScriptRoot "..\release"),
    [switch]$SkipFrontendBuild
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$frontendDist = Join-Path $projectRoot "frontend\dist"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$packageRoot = Join-Path $OutputDir "software-cup-demo-$stamp"
$zipPath = "$packageRoot.zip"

if (-not $SkipFrontendBuild) {
    & (Join-Path $PSScriptRoot "build-frontend.ps1")
}

if (-not (Test-Path $frontendDist)) {
    throw "frontend/dist does not exist. Run scripts/build-frontend.ps1 first."
}

New-Item -ItemType Directory -Force -Path $packageRoot | Out-Null

$include = @(
    "backend",
    "data\examples",
    "docs",
    "frontend\dist",
    "scripts",
    ".env.example",
    "README.md",
    "start-dev.bat",
    "configure-api.bat"
)

foreach ($item in $include) {
    $source = Join-Path $projectRoot $item
    if (Test-Path $source) {
        $target = Join-Path $packageRoot $item
        New-Item -ItemType Directory -Force -Path (Split-Path $target -Parent) | Out-Null
        Copy-Item -Path $source -Destination $target -Recurse -Force
    }
}

if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $zipPath -Force

Write-Host "[package] Demo package ready: $zipPath"
Write-Host "[package] Upload this zip to Kylin/LoongArch, then run the backend with SERVE_FRONTEND=auto."
