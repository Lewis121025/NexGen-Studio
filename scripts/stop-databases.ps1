# Lewis AI System - Stop Databases

Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "  Lewis AI System - Stop Databases" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

try {
    docker --version | Out-Null
} catch {
    Write-Host "[error] Docker is not installed or not on PATH." -ForegroundColor Red
    exit 1
}

# Check running database services
$runningServices = docker compose ps postgres redis weaviate --format json | ConvertFrom-Json | Where-Object { $_.State -eq "running" }

if (-not $runningServices) {
    Write-Host "[info] No database services are currently running" -ForegroundColor Yellow
    exit 0
}

Write-Host "[info] Currently running services:" -ForegroundColor Yellow
docker compose ps postgres redis weaviate
Write-Host ""

Write-Host "[info] Stopping database services (volumes preserved)..." -ForegroundColor Yellow
docker compose stop postgres redis weaviate

if ($LASTEXITCODE -ne 0) {
    Write-Host "[warn] docker compose stop failed, attempting docker compose down (volumes preserved)..." -ForegroundColor Yellow
    docker compose down
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "[error] Failed to stop services" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=======================================" -ForegroundColor Green
Write-Host "  ✅ Database services stopped" -ForegroundColor Green
Write-Host "=======================================" -ForegroundColor Green
Write-Host ""

Write-Host "[info] Data volumes preserved, data is safe" -ForegroundColor Cyan
Write-Host "[info] Restart with: .\\scripts\\start-databases.ps1" -ForegroundColor Gray
Write-Host ""
