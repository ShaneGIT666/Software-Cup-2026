param(
    [ValidateSet("offline", "llm")]
    [string]$Mode = "",
    [string]$BaseUrl = "",
    [string]$Model = "",
    [string]$ApiKey = "",
    [switch]$Force,
    [switch]$UnsafeNoAuth,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$EnvPath = Join-Path $Root ".env"
$GitIgnorePath = Join-Path $Root ".gitignore"

function Show-Help {
    Write-Host "Initialize local configuration for Software Cup maintenance assistant."
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\init-config.ps1 -Mode offline"
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\init-config.ps1 -Mode llm -BaseUrl <url> -Model <model>"
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\init-config.ps1 -Mode offline -UnsafeNoAuth"
    Write-Host ""
    Write-Host "Modes:"
    Write-Host "  offline  Demo fallback mode without remote API keys."
    Write-Host "  llm      Real OpenAI-compatible LLM mode."
    Write-Host ""
    Write-Host "Safety:"
    Write-Host "  The script writes only local .env, backs up existing .env first, and masks API keys in output."
    Write-Host "  UnsafeNoAuth is for local loopback-only demonstration and must not be used for competition delivery."
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

function New-SecureToken {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    }
    finally {
        $rng.Dispose()
    }
    return -join ($bytes | ForEach-Object { $_.ToString("x2") })
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

$authLines = if ($UnsafeNoAuth) {
    @(
        "APP_ENV=development",
        "AUTH_MODE=off",
        "ALLOW_INSECURE_AUTH_OFF=true"
    )
} else {
    $OperatorToken = New-SecureToken
    $ReviewerToken = New-SecureToken
    $AdminToken = New-SecureToken
    @(
        "APP_ENV=competition",
        "AUTH_MODE=token",
        "ALLOW_INSECURE_AUTH_OFF=false",
        "AUTH_OPERATOR_TOKEN=$OperatorToken",
        "AUTH_REVIEWER_TOKEN=$ReviewerToken",
        "AUTH_ADMIN_TOKEN=$AdminToken"
    )
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
    $lines = @($authLines + @(
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
    ))
} else {
    $lines = @($authLines + @(
        "REMOTE_API_MODE=off",
        "LLM_PROVIDER=mock",
        "MULTIMODAL_PROVIDER=mock",
        "OCR_PROVIDER=mock",
        "RAG_VECTOR_FALLBACK_LOCAL=on"
    ))
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
if (-not $UnsafeNoAuth) {
    Write-Host "  Operator token: $(Mask-Key $OperatorToken)"
    Write-Host "  Reviewer token: $(Mask-Key $ReviewerToken)"
    Write-Host "  Admin token: $(Mask-Key $AdminToken)"
}
Write-Host ""
Write-Host "Next start commands:"
$HostAddress = if ($UnsafeNoAuth) { "127.0.0.1" } else { "0.0.0.0" }
Write-Host "  .\backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host $HostAddress --port 8000"
Write-Host "  cd frontend; npm.cmd run dev"
Write-Host ""
Write-Host "Validate provider status:"
Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\validate-provider.ps1"
Write-Host "  Or open /api/providers/status and the System Status page."
Write-Host ""
Write-Host "Restore offline demo fallback:"
Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\init-config.ps1 -Mode offline -Force"
