param(
    [ValidateSet("offline", "llm")]
    [string]$Mode = "",
    [string]$BaseUrl = "",
    [string]$Model = "",
    [string]$ApiKey = "",
    [switch]$Force,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$EnvPath = Join-Path $Root ".env"
$GitIgnorePath = Join-Path $Root ".gitignore"

function Show-Help {
    Write-Host "Initialize legacy prototype Provider/mock configuration only."
    Write-Warning "This script does not generate PostgreSQL, M1 identity, idempotency, controlled-storage, or production deployment configuration."
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\init-config.ps1 -Mode offline"
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\init-config.ps1 -Mode llm -BaseUrl <url> -Model <model>"
    Write-Host ""
    Write-Host "Modes:"
    Write-Host "  offline  Demo fallback mode without remote API keys."
    Write-Host "  llm      Real OpenAI-compatible LLM mode."
    Write-Host ""
    Write-Host "Safety:"
    Write-Host "  The script writes only local .env, backs up existing .env first, and masks API keys in output."
}

function Mask-Key([string]$Key) {
    if ([string]::IsNullOrWhiteSpace($Key)) {
        return "not configured"
    }
    if ($Key.Length -le 8) {
        return "****"
    }
    return "$($Key.Substring(0, 3))****$($Key.Substring($Key.Length - 4))"
}

function Ensure-GitIgnore {
    if (-not (Test-Path $GitIgnorePath)) {
        Set-Content -LiteralPath $GitIgnorePath -Value ".env`n.env.*`n!.env.example`n" -Encoding UTF8
        return
    }

    $content = Get-Content -LiteralPath $GitIgnorePath -Raw
    if ($content -notmatch "(?m)^\.env$") {
        Add-Content -LiteralPath $GitIgnorePath -Value "`n# Local environment`n.env" -Encoding UTF8
    }
    if ($content -notmatch "(?m)^\.env\.\*$") {
        Add-Content -LiteralPath $GitIgnorePath -Value ".env.*" -Encoding UTF8
    }
}

if ($Help) {
    Show-Help
    exit 0
}

Write-Warning "Legacy prototype configuration only; this is not a product or production configuration initializer."

if (-not $Mode) {
    Write-Host "Select run mode:"
    Write-Host "  1. Offline demo fallback"
    Write-Host "  2. Real LLM"
    $choice = Read-Host "Enter 1 or 2"
    $Mode = if ($choice -eq "2") { "llm" } else { "offline" }
}

Ensure-GitIgnore

if ((Test-Path $EnvPath) -and -not $Force) {
    $confirm = Read-Host ".env already exists. Type yes to back it up and overwrite"
    if ($confirm -ne "yes") {
        Write-Host "Cancelled. .env was not modified."
        exit 0
    }
}

if (Test-Path $EnvPath) {
    $timestamp = Get-Date -Format "yyyyMMddHHmmss"
    $backup = Join-Path $Root ".env.backup.$timestamp"
    Copy-Item -LiteralPath $EnvPath -Destination $backup -Force
    Write-Host "Backed up existing .env to $backup"
}

if ($Mode -eq "llm") {
    if (-not $BaseUrl) {
        $BaseUrl = Read-Host "OpenAI-compatible Base URL"
    }
    if (-not $Model) {
        $Model = Read-Host "Model name"
    }
    if (-not $ApiKey) {
        $secureKey = Read-Host "API Key" -AsSecureString
        $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
        try {
            $ApiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
        } finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
        }
    }
    $lines = @(
        "REMOTE_API_MODE=auto",
        "LLM_PROVIDER=openai",
        "OPENAI_BASE_URL=$BaseUrl",
        "OPENAI_API_STYLE=chat_completions",
        "OPENAI_MODEL=$Model",
        "OPENAI_API_KEY=$ApiKey",
        "LLM_TIMEOUT_SECONDS=60",
        "RAG_USE_STRUCTURED_LLM_ANSWER=true",
        "MULTIMODAL_PROVIDER=mock",
        "OCR_PROVIDER=mock",
        "RAG_VECTOR_FALLBACK_LOCAL=on"
    )
} else {
    $lines = @(
        "REMOTE_API_MODE=off",
        "LLM_PROVIDER=mock",
        "MULTIMODAL_PROVIDER=mock",
        "OCR_PROVIDER=mock",
        "RAG_VECTOR_FALLBACK_LOCAL=on"
    )
}

Set-Content -LiteralPath $EnvPath -Value ($lines -join "`n") -Encoding UTF8

$displayBaseUrl = if ($Mode -eq "llm") { $BaseUrl } else { "not used" }
$displayModel = if ($Mode -eq "llm") { $Model } else { "mock" }

Write-Host ""
Write-Host "Local .env has been written."
Write-Host "Summary:"
Write-Host "  Mode: $Mode"
Write-Host "  Base URL: $displayBaseUrl"
Write-Host "  Model: $displayModel"
Write-Host "  API Key: $(Mask-Key $ApiKey)"
Write-Host ""
Write-Host "Windows development start (legacy prototype only):"
Write-Host "  .\dev.bat start"
Write-Host ""
Write-Host "Validate provider status:"
Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\validate-provider.ps1"
Write-Host "  Or open /api/providers/status and the System Status page."
Write-Host ""
Write-Host "Restore offline demo fallback:"
Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\init-config.ps1 -Mode offline -Force"
