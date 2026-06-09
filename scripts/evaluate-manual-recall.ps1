param(
    [string]$ManualPath = "E:\Download\Downloads\摩托车发动机维修手册.pdf",
    [string]$TopKs = "1,3,5",
    [ValidateSet("text", "json")]
    [string]$Format = "text"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Backend virtualenv python not found: $Python"
}

& $Python (Join-Path $PSScriptRoot "evaluate_manual_recall.py") --manual $ManualPath --topks $TopKs --format $Format
