param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [string]$EnvName = "software-cup-2026"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendScript = Join-Path $PSScriptRoot "start-backend.ps1"
$FrontendScript = Join-Path $PSScriptRoot "start-frontend.ps1"

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

Write-Host "Development servers are starting in background jobs." -ForegroundColor Green
Write-Host "Use this page after Vite is ready: http://localhost:$FrontendPort"
Write-Host ""
Write-Host "Useful commands:"
Write-Host "  Get-Job software-cup-* -WarningAction SilentlyContinue"
Write-Host "  Receive-Job software-cup-backend -Keep"
Write-Host "  Receive-Job software-cup-frontend -Keep"
Write-Host "  Stop-Job software-cup-* -WarningAction SilentlyContinue; Remove-Job software-cup-* -WarningAction SilentlyContinue"
Write-Host ""
Start-Sleep -Seconds 2
Get-Job software-cup-* -WarningAction SilentlyContinue | Select-Object Name, State, HasMoreData
