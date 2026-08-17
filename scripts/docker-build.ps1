param(
    [string]$ImageName = "software-cup-demo:loongarch",
    [string]$BaseImage = "cr.loongnix.cn/library/python:3.11",
    [switch]$SkipFrontendBuild
)

# Historical LoongArch/demo prototype only; not a production or release build.

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

if (-not $SkipFrontendBuild) {
    & (Join-Path $PSScriptRoot "build-frontend.ps1")
}

$FrontendDist = Join-Path $ProjectRoot "frontend\dist\index.html"
if (-not (Test-Path $FrontendDist)) {
    throw "frontend/dist/index.html does not exist. Build frontend before docker build."
}

docker build `
    --build-arg BASE_IMAGE=$BaseImage `
    -t $ImageName `
    $ProjectRoot
