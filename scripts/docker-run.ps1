param(
    [string]$ImageName = "software-cup-demo:loongarch",
    [string]$ContainerName = "software-cup-demo",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$existing = docker ps -aq --filter "name=^/$ContainerName$"
if ($existing) {
    docker rm -f $ContainerName | Out-Null
}

docker run -d `
    --name $ContainerName `
    -p "${Port}:8000" `
    -e REMOTE_API_MODE=off `
    -e RAG_VECTOR_STORE=off `
    -v "software-cup-runtime:/app/runtime" `
    $ImageName

Write-Host "[docker] Container started: $ContainerName"
Write-Host "[docker] Health: http://127.0.0.1:$Port/api/health"
