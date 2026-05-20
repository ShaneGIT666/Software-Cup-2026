param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [string]$EnvName = "software-cup-2026"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendScript = Join-Path $PSScriptRoot "start-backend.ps1"
$FrontendScript = Join-Path $PSScriptRoot "start-frontend.ps1"
$RuntimeDir = Join-Path $RepoRoot ".dev-runtime"
$PidFile = Join-Path $RuntimeDir "dev-processes.json"

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

Write-Host "Starting backend and frontend development servers..." -ForegroundColor Cyan
Write-Host "Backend:  http://127.0.0.1:$BackendPort"
Write-Host "Frontend: http://127.0.0.1:$FrontendPort"
Write-Host ""

$backendJob = Start-Job -Name "software-cup-backend" -ScriptBlock {
    param($ScriptPath, $RepoRoot, $Port, $EnvName)
    Set-Location $RepoRoot
    powershell -ExecutionPolicy Bypass -File $ScriptPath -Port $Port -EnvName $EnvName
} -ArgumentList $BackendScript, $RepoRoot, $BackendPort, $EnvName

$frontendJob = Start-Job -Name "software-cup-frontend" -ScriptBlock {
    param($ScriptPath, $RepoRoot, $Port)
    Set-Location $RepoRoot
    powershell -ExecutionPolicy Bypass -File $ScriptPath -Port $Port
} -ArgumentList $FrontendScript, $RepoRoot, $FrontendPort

@{
    backend = @{
        jobId = $backendJob.Id
        port = $BackendPort
    }
    frontend = @{
        jobId = $frontendJob.Id
        port = $FrontendPort
    }
} | ConvertTo-Json -Depth 3 | Set-Content -Path $PidFile -Encoding UTF8

Write-Host "Development servers are starting in this PowerShell session." -ForegroundColor Green
Write-Host "Use this page after Vite is ready: http://localhost:$FrontendPort"
Write-Host ""
Write-Host "Keep this terminal open. Press Ctrl+C to stop both servers." -ForegroundColor Yellow
Write-Host ""

try {
    while ($true) {
        Receive-Job $backendJob -ErrorAction SilentlyContinue
        Receive-Job $frontendJob -ErrorAction SilentlyContinue

        $failedJobs = @($backendJob, $frontendJob) | Where-Object { $_.State -in @("Failed", "Stopped", "Completed") }
        if ($failedJobs.Count -gt 0) {
            $failedJobs | Select-Object Name, State | Format-Table
            throw "One or more development servers stopped unexpectedly."
        }

        Start-Sleep -Seconds 2
    }
}
finally {
    Stop-Job $backendJob, $frontendJob -ErrorAction SilentlyContinue
    Remove-Job $backendJob, $frontendJob -ErrorAction SilentlyContinue
    if (Test-Path $PidFile) {
        Remove-Item -LiteralPath $PidFile -Force
    }
    Write-Host "Development servers stopped."
}
