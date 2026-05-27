param(
    [int]$Port = 8000,
    [string]$EnvName = "software-cup-2026"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $RepoRoot "backend"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
$EnvFile = Join-Path $RepoRoot ".env"

if (Test-Path $EnvFile) {
    Get-Content -Path $EnvFile -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }
        $parts = $line.Split("=", 2)
        [Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1], "Process")
    }
    Write-Host "Loaded local environment from .env" -ForegroundColor DarkGreen
}

if (-not (Test-Path $VenvPython)) {
    & $PSScriptRoot\setup-anaconda.ps1 -EnvName $EnvName
}

& $VenvPython -m uvicorn app.main:app --reload --host 127.0.0.1 --port $Port --app-dir $BackendDir
