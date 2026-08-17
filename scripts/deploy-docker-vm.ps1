param(
    [string]$HostName = "frp-use.com",
    [int]$Port = 21924,
    [string]$User = "vmuser",
    [string]$IdentityFile = (Join-Path $env:USERPROFILE ".ssh\software_cup_kylin_vm"),
    [string]$RemoteDir = "/home/vmuser/software-cup-docker",
    [string]$RepoUrl = "https://github.com/ShaneGIT666/Software-Cup-2026",
    [string]$Branch = "main",
    [string]$PackageUrl = "",
    [string]$ImageName = "software-cup-demo:loongarch",
    [string]$ContainerName = "software-cup-demo",
    [int]$AppPort = 8000,
    [string]$BaseImage = "cr.loongnix.cn/library/python:3.11",
    [switch]$SkipLocalFrontendBuild,
    [switch]$NonInteractiveSsh
)

# Historical remote demo deployment only; not a supported product deployment
# or evidence for the Windows default / Ubuntu CI target.

$ErrorActionPreference = "Stop"

function Invoke-Remote {
    param([string]$Command)
    $sshArgs = @("-i", $IdentityFile, "-p", $Port, "-o", "ConnectTimeout=15")
    if ($NonInteractiveSsh) {
        $sshArgs += @("-o", "BatchMode=yes")
    }
    $sshArgs += @("$User@$HostName", $Command)
    & ssh @sshArgs
}

function Escape-BashSingleQuote {
    param([string]$Value)
    return $Value -replace "'", "'\''"
}

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$frontendIndex = Join-Path $projectRoot "frontend\dist\index.html"

if (-not $SkipLocalFrontendBuild) {
    & (Join-Path $PSScriptRoot "build-frontend.ps1")
}

if (-not (Test-Path $frontendIndex)) {
    throw "frontend/dist/index.html does not exist. Build the frontend before Docker deployment."
}

Write-Host "[deploy] Local frontend dist is ready: $frontendIndex"
Write-Host "[deploy] Checking remote Docker environment on $User@${HostName}:$Port ..."

$probe = Invoke-Remote "uname -m && hostname && (systemctl is-active docker || true) && sudo -n docker info --format '{{.Architecture}} {{.OSType}} {{.ServerVersion}}'"
Write-Host $probe

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[deploy] Remote sudo docker is not available without an interactive password."
    Write-Host "[deploy] Run this once in the VM terminal, then re-run this script:"
    Write-Host "        sudo systemctl start docker"
    Write-Host "        sudo docker info"
    Write-Host ""
    throw "Remote Docker precheck failed. No password was stored or transmitted."
}

$repoArchiveUrl = "$($RepoUrl.TrimEnd('/'))/archive/refs/heads/$Branch.zip"
$sourceUrl = if ($PackageUrl.Trim()) { $PackageUrl.Trim() } else { $repoArchiveUrl }

$remoteScript = @"
set -euo pipefail

REMOTE_DIR='$(Escape-BashSingleQuote $RemoteDir)'
SOURCE_URL='$(Escape-BashSingleQuote $sourceUrl)'
BRANCH='$(Escape-BashSingleQuote $Branch)'
IMAGE_NAME='$(Escape-BashSingleQuote $ImageName)'
CONTAINER_NAME='$(Escape-BashSingleQuote $ContainerName)'
APP_PORT='$(Escape-BashSingleQuote ([string]$AppPort))'
BASE_IMAGE='$(Escape-BashSingleQuote $BaseImage)'

echo "[deploy] Preparing remote directory: `$REMOTE_DIR"
mkdir -p "`$REMOTE_DIR"
cd "`$REMOTE_DIR"
rm -rf source source.zip source-unpacked

echo "[deploy] Downloading source package: `$SOURCE_URL"
curl -fL "`$SOURCE_URL" -o source.zip
unzip -q source.zip -d source-unpacked
if [ -f source-unpacked/Dockerfile ]; then
  mv source-unpacked source
else
  first_dir=`$(find source-unpacked -mindepth 1 -maxdepth 1 -type d | head -n 1)
  if [ -z "`$first_dir" ]; then
    echo "[deploy] ERROR: downloaded zip does not contain a project directory."
    exit 11
  fi
  mv "`$first_dir" source
  rm -rf source-unpacked
fi
rm -rf source-unpacked source.zip

cd source
if [ ! -f Dockerfile ]; then
  echo "[deploy] ERROR: Dockerfile is missing from the downloaded package."
  exit 12
fi

if [ ! -f frontend/dist/index.html ]; then
  echo "[deploy] ERROR: frontend/dist/index.html is missing."
  echo "[deploy] The VM has no npm, so it cannot build the frontend from source."
  echo "[deploy] Use a GitHub Release/Artifact package that includes frontend/dist, then pass -PackageUrl <zip-url>."
  exit 13
fi

echo "[deploy] Building Docker image: `$IMAGE_NAME"
sudo -n docker build --build-arg BASE_IMAGE="`$BASE_IMAGE" -t "`$IMAGE_NAME" .

echo "[deploy] Restarting container: `$CONTAINER_NAME"
if sudo -n docker ps -aq --filter "name=^/`$CONTAINER_NAME`$" | grep -q .; then
  sudo -n docker rm -f "`$CONTAINER_NAME" >/dev/null
fi

sudo -n docker run -d \
  --name "`$CONTAINER_NAME" \
  -p "`$APP_PORT:8000" \
  -e SERVE_FRONTEND=auto \
  -e FRONTEND_DIST_DIR=/app/frontend/dist \
  -e REMOTE_API_MODE=off \
  -e LLM_PROVIDER=mock \
  -e MULTIMODAL_PROVIDER=mock \
  -e RAG_VECTOR_STORE=off \
  -v software-cup-runtime:/app/runtime \
  "`$IMAGE_NAME"

echo "[deploy] Waiting for API startup..."
sleep 3
curl -fsS "http://127.0.0.1:`$APP_PORT/api/health"
echo
curl -fsS "http://127.0.0.1:`$APP_PORT/api/providers/status"
echo
curl -fsS "http://127.0.0.1:`$APP_PORT/" | head -c 160
echo
echo "[deploy] Docker deployment verification finished."
"@

$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remoteScript))
$command = "printf '%s' '$encoded' | base64 -d | bash"
Invoke-Remote $command

Write-Host "[deploy] Done. Open http://${HostName}:$AppPort/ only if your FRP rule exposes this port; otherwise access it inside the VM with http://127.0.0.1:$AppPort/."
