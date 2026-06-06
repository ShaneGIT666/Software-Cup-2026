param(
    [ValidateSet("start", "stop", "restart", "status", "verify", "logs")]
    [string]$Action = "status",
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [string]$EnvName = "software-cup-2026",
    [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$PreferredRuntimeDir = Join-Path $RepoRoot ".dev-runtime"
$FallbackRuntimeDir = Join-Path ([System.IO.Path]::GetTempPath()) "software-cup-2026-dev-runtime"

function Initialize-RuntimeDir {
    foreach ($candidate in @($PreferredRuntimeDir, $FallbackRuntimeDir)) {
        try {
            New-Item -ItemType Directory -Force -Path $candidate | Out-Null
            $probe = Join-Path $candidate ".write-test"
            Set-Content -Path $probe -Value "ok" -Encoding UTF8
            Remove-Item -LiteralPath $probe -Force
            return $candidate
        }
        catch {
            Write-Host "Runtime directory is not writable: $candidate" -ForegroundColor Yellow
        }
    }

    throw "No writable runtime directory is available."
}

$RuntimeDir = Initialize-RuntimeDir
$StateFile = Join-Path $RuntimeDir "dev-services.json"
$BackendLog = Join-Path $RuntimeDir "backend.log"
$BackendErr = Join-Path $RuntimeDir "backend.err.log"
$FrontendLog = Join-Path $RuntimeDir "frontend.log"
$FrontendErr = Join-Path $RuntimeDir "frontend.err.log"

function Write-Section {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Get-ProcessBySavedId {
    param([object]$Entry)
    if (-not $Entry -or -not $Entry.pid) {
        return $null
    }
    return Get-Process -Id ([int]$Entry.pid) -ErrorAction SilentlyContinue
}

function Get-State {
    if (-not (Test-Path $StateFile)) {
        return $null
    }
    try {
        return Get-Content $StateFile -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        return $null
    }
}

function Save-State {
    param(
        [System.Diagnostics.Process]$BackendProcess,
        [System.Diagnostics.Process]$FrontendProcess
    )

    New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
    @{
        startedAt = (Get-Date).ToString("s")
        backend = @{
            pid = $BackendProcess.Id
            port = $BackendPort
            url = "http://127.0.0.1:$BackendPort/api/health"
            log = $BackendLog
            err = $BackendErr
        }
        frontend = @{
            pid = $FrontendProcess.Id
            port = $FrontendPort
            url = "http://127.0.0.1:$FrontendPort/"
            log = $FrontendLog
            err = $FrontendErr
        }
    } | ConvertTo-Json -Depth 4 | Set-Content -Path $StateFile -Encoding UTF8
}

function Test-Port {
    param([int]$Port)
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(700)) {
            return $false
        }
        $client.EndConnect($async)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Stop-SavedServices {
    $state = Get-State
    if ($state) {
        foreach ($entry in @($state.backend, $state.frontend)) {
            $process = Get-ProcessBySavedId -Entry $entry
            if ($process) {
                Write-Host "Stopping process $($process.Id)..." -ForegroundColor Yellow
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            }
        }
    }

    foreach ($port in @($BackendPort, $FrontendPort)) {
        $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        foreach ($connection in $connections) {
            if ($connection.OwningProcess) {
                Write-Host "Stopping process on port $port (PID $($connection.OwningProcess))..." -ForegroundColor Yellow
                Stop-Process -Id ([int]$connection.OwningProcess) -Force -ErrorAction SilentlyContinue
            }
        }
    }

    if (Test-Path $StateFile) {
        Remove-Item -LiteralPath $StateFile -Force
    }
}

function Start-ServiceProcess {
    param(
        [string]$Name,
        [string]$Script,
        [string]$Arguments,
        [string]$OutLog,
        [string]$ErrLog
    )

    $wrapper = Join-Path $RuntimeDir "$Name-run.ps1"
    $escapedRepoRoot = $RepoRoot.ToString().Replace("'", "''")
    $escapedScript = $Script.Replace("'", "''")
    $escapedOutLog = $OutLog.Replace("'", "''")
    $escapedErrLog = $ErrLog.Replace("'", "''")
    @"
Set-Location -LiteralPath '$escapedRepoRoot'
& '$escapedScript' $Arguments 1> '$escapedOutLog' 2> '$escapedErrLog'
"@ | Set-Content -Path $wrapper -Encoding UTF8

    Write-Host "Starting $Name..." -ForegroundColor Green
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = "powershell.exe"
    $startInfo.Arguments = "-NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$wrapper`""
    $startInfo.WorkingDirectory = $RepoRoot
    $startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $startInfo.UseShellExecute = $true
    return [System.Diagnostics.Process]::Start($startInfo)
}

function Start-DevServices {
    New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

    if ((Test-Port -Port $BackendPort) -or (Test-Port -Port $FrontendPort)) {
        Write-Host "Port $BackendPort or $FrontendPort is already in use. Run 'dev stop' first if these are stale." -ForegroundColor Yellow
        Show-Status
        return
    }

    $backendScript = Join-Path $PSScriptRoot "start-backend.ps1"
    $frontendScript = Join-Path $PSScriptRoot "start-frontend.ps1"

    $backend = Start-ServiceProcess `
        -Name "backend" `
        -Script $backendScript `
        -Arguments "-Port $BackendPort -EnvName `"$EnvName`"" `
        -OutLog $BackendLog `
        -ErrLog $BackendErr

    $frontend = Start-ServiceProcess `
        -Name "frontend" `
        -Script $frontendScript `
        -Arguments "-Port $FrontendPort" `
        -OutLog $FrontendLog `
        -ErrLog $FrontendErr

    Save-State -BackendProcess $backend -FrontendProcess $frontend
    Write-Host "Services are starting." -ForegroundColor Green
    Write-Host "Frontend: http://127.0.0.1:$FrontendPort/"
    Write-Host "Backend:  http://127.0.0.1:$BackendPort/api/health"

    if ($OpenBrowser) {
        Start-Process "http://127.0.0.1:$FrontendPort/"
    }
}

function Show-Status {
    $state = Get-State
    $backendProcess = Get-ProcessBySavedId -Entry $state.backend
    $frontendProcess = Get-ProcessBySavedId -Entry $state.frontend
    $backendPortOpen = Test-Port -Port $BackendPort
    $frontendPortOpen = Test-Port -Port $FrontendPort

    Write-Section "Development service status"
    [PSCustomObject]@{
        Service = "backend"
        Pid = if ($backendProcess) { $backendProcess.Id } else { "" }
        Process = if ($backendProcess) { "running" } else { "stopped" }
        Port = $BackendPort
        Listening = $backendPortOpen
        Url = "http://127.0.0.1:$BackendPort/api/health"
    } | Format-List

    [PSCustomObject]@{
        Service = "frontend"
        Pid = if ($frontendProcess) { $frontendProcess.Id } else { "" }
        Process = if ($frontendProcess) { "running" } else { "stopped" }
        Port = $FrontendPort
        Listening = $frontendPortOpen
        Url = "http://127.0.0.1:$FrontendPort/"
    } | Format-List

    if ($state) {
        Write-Host "State file: $StateFile"
    }
}

function Invoke-HealthChecks {
    Write-Section "Health checks"

    $backend = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/api/health" -TimeoutSec 6
    if (-not $backend.success -or $backend.data.status -ne "ok") {
        throw "Backend health check failed."
    }
    Write-Host "Backend OK: http://127.0.0.1:$BackendPort/api/health" -ForegroundColor Green

    $frontend = Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort/" -UseBasicParsing -TimeoutSec 6
    if ($frontend.StatusCode -lt 200 -or $frontend.StatusCode -ge 400) {
        throw "Frontend check failed with status $($frontend.StatusCode)."
    }
    Write-Host "Frontend OK: http://127.0.0.1:$FrontendPort/" -ForegroundColor Green
}

function Show-Logs {
    Write-Section "Backend log"
    if (Test-Path $BackendLog) { Get-Content -Tail 60 $BackendLog }
    if (Test-Path $BackendErr) { Get-Content -Tail 60 $BackendErr }

    Write-Section "Frontend log"
    if (Test-Path $FrontendLog) { Get-Content -Tail 60 $FrontendLog }
    if (Test-Path $FrontendErr) { Get-Content -Tail 60 $FrontendErr }
}

switch ($Action) {
    "start" {
        Start-DevServices
    }
    "stop" {
        Stop-SavedServices
        Write-Host "Development services stopped." -ForegroundColor Green
    }
    "restart" {
        Stop-SavedServices
        Start-Sleep -Seconds 1
        Start-DevServices
    }
    "status" {
        Show-Status
    }
    "verify" {
        Invoke-HealthChecks
    }
    "logs" {
        Show-Logs
    }
}
