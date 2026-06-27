param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Write-Host "Validate backend provider status."
    Write-Host "Usage:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\validate-provider.ps1 [-BaseUrl http://127.0.0.1:8000]"
    Write-Host ""
    Write-Host "The script calls /api/providers/status and never prints API keys."
    exit 0
}

try {
    $status = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/providers/status" -TimeoutSec 20
    $data = $status.data
    Write-Host "Provider status summary:"
    Write-Host "  remoteApiMode: $($data.remoteApiMode)"
    Write-Host "  offlineFallback: $($data.offlineFallback)"
    Write-Host "  llm: $($data.llm.effectiveProvider) / model=$($data.llm.model) / keyConfigured=$($data.llm.keyConfigured)"
    Write-Host "  multimodal: $($data.multimodal.effectiveProvider)"
    Write-Host "  ocr: $($data.ocr.effectiveProvider)"
    Write-Host "  embedding: $($data.embedding.effectiveProvider) / vectorStore=$($data.embedding.vectorStore)"
} catch {
    Write-Host "Backend service is not available. Please confirm it is running."
    exit 1
}
