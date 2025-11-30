# Auto start Lewis AI System (backend + frontend) using Docker Compose
# Usage:
#   pwsh scripts/auto-start.ps1
#   pwsh scripts/auto-start.ps1 -Rebuild
# Params:
#   -Rebuild     Force docker compose build
#   -Retries     Max retry count when waiting for health (default 40)
#   -OpenBrowser Open docs/front after start (default: true)

[CmdletBinding()]
param(
    [switch]$Rebuild = $false,
    [int]$Retries = 40,
    [switch]$OpenBrowser = $true
)

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[ERR ] $msg" -ForegroundColor Red }

# 1) Basic checks
if (-not (Test-Path ".env")) {
    Write-Err ".env not found. Please copy .env.docker.example or provide secrets first."
    exit 1
}

try { docker --version | Out-Null } catch {
    Write-Err "Docker is not available. Start Docker Desktop first."
    exit 1
}

try { docker compose version | Out-Null } catch {
    Write-Err "'docker compose' command not found (needs Docker Desktop >= 4.18)."
    exit 1
}

# 2) Optional rebuild
if ($Rebuild) {
    Write-Info "Rebuilding images..."
    docker compose build
    if ($LASTEXITCODE -ne 0) { Write-Err "Build failed"; exit 1 }
}

# 3) Start backing services first (db/cache/vector)
Write-Info "Starting infra services (postgres, redis, weaviate)..."
docker compose up -d postgres redis weaviate
if ($LASTEXITCODE -ne 0) { Write-Err "Failed to start infra services"; exit 1 }

# 4) Init DB schema
Write-Info "Running DB migrations..."
docker compose run --rm -e SKIP_ENTRYPOINT_DB_INIT=1 lewis-api python3 -m lewis_ai_system.cli init-db
if ($LASTEXITCODE -ne 0) { Write-Err "DB init failed"; exit 1 }

# 5) Start backend + frontend
Write-Info "Starting API + frontend..."
docker compose up -d lewis-api frontend
if ($LASTEXITCODE -ne 0) { Write-Err "Service startup failed"; exit 1 }

# 6) Wait for health
function Wait-Ready([string]$name, [string]$url) {
    for ($i = 1; $i -le $Retries; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($resp.StatusCode -eq 200) {
                Write-Info "$name ready ($url)"
                return $true
            }
        } catch {}
        Start-Sleep -Seconds 1
    }
    return $false
}

$apiReady = Wait-Ready "API" "http://localhost:8000/healthz"
$frontReady = Wait-Ready "Frontend" "http://localhost:3000"

if (-not $apiReady -or -not $frontReady) {
    Write-Warn "Services did not pass health check. Inspect logs:"
    Write-Warn "  docker compose logs -f lewis-api"
    Write-Warn "  docker compose logs -f frontend"
    exit 1
}

# 7) Success info
Write-Host ""
Write-Host "================ Lewis AI System Ready ================" -ForegroundColor Green
Write-Info "API        : http://localhost:8000 (docs: /docs)"
Write-Info "Frontend   : http://localhost:3000"
Write-Info "Logs       : docker compose logs -f"
Write-Info "Stop       : docker compose down"

if ($OpenBrowser) {
    try { Start-Process "http://localhost:3000" } catch {}
    try { Start-Process "http://localhost:8000/docs" } catch {}
}
