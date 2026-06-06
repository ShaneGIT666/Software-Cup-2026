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

function Copy-DemoItem {
    param(
        [string]$Source,
        [string]$Target
    )

    New-Item -ItemType Directory -Force -Path (Split-Path $Target -Parent) | Out-Null

    if ((Get-Item $Source).PSIsContainer) {
        New-Item -ItemType Directory -Force -Path $Target | Out-Null
        $excludeDirs = @(".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache")
        $excludeFiles = @("*.pyc", "*.pyo", "*.log")
        & robocopy $Source $Target /E /XD $excludeDirs /XF $excludeFiles /NFL /NDL /NJH /NJS /NC /NS | Out-Null
        if ($LASTEXITCODE -gt 7) {
            throw "robocopy failed with exit code $LASTEXITCODE while copying $Source"
        }
    }
    else {
        Copy-Item -Path $Source -Destination $Target -Force
    }
}

$include = @(
    "backend",
    "data\examples",
    "docs",
    "frontend\dist",
    "scripts",
    "Dockerfile",
    ".dockerignore",
    ".env.example",
    "README.md",
    "start-dev.bat",
    "configure-api.bat"
)

foreach ($item in $include) {
    $source = Join-Path $projectRoot $item
    if (Test-Path $source) {
        $target = Join-Path $packageRoot $item
        Copy-DemoItem -Source $source -Target $target
    }
}

if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $zipPath -Force

Write-Host "[package] Demo package ready: $zipPath"
Write-Host "[package] Upload this zip to Kylin/LoongArch, then run the backend with SERVE_FRONTEND=auto."
