# Lewis AI System - 数据库初始化脚本
# 在数据库服务运行后执行表结构初始化

Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Lewis AI System - 数据库初始化" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# 检查.env文件
if (-not (Test-Path ".env")) {
    Write-Host "✗ .env 文件不存在！" -ForegroundColor Red
    Write-Host "请先创建 .env 文件并配置 DATABASE_URL" -ForegroundColor Yellow
    exit 1
}

# 检查数据库服务是否运行
Write-Host "🔍 检查数据库服务状态..." -ForegroundColor Yellow

$postgresRunning = docker compose ps postgres --format json | ConvertFrom-Json | Where-Object { $_.State -eq "running" }
if (-not $postgresRunning) {
    Write-Host "✗ PostgreSQL 服务未运行" -ForegroundColor Red
    Write-Host "请先运行: .\scripts\start-databases.ps1" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ PostgreSQL 服务正在运行" -ForegroundColor Green

# 等待数据库完全就绪
Write-Host "⏳ 等待数据库连接就绪..." -ForegroundColor Yellow
$maxRetries = 20
$retryCount = 0
$dbReady = $false

while ($retryCount -lt $maxRetries) {
    try {
        $result = docker compose exec -T postgres pg_isready -U lewis 2>&1
        if ($LASTEXITCODE -eq 0) {
            $dbReady = $true
            break
        }
    } catch {
        # 继续重试
    }
    $retryCount++
    Start-Sleep -Seconds 1
}

if (-not $dbReady) {
    Write-Host "✗ 数据库未能在预期时间内就绪" -ForegroundColor Red
    exit 1
}

Write-Host "✓ 数据库连接就绪" -ForegroundColor Green
Write-Host ""

# 检查是否需要构建镜像
Write-Host "🔨 检查应用镜像..." -ForegroundColor Yellow
$imageExists = docker images --format "{{.Repository}}:{{.Tag}}" | Select-String "lewis-ai-system-lewis-api"
if (-not $imageExists) {
    Write-Host "📦 构建应用镜像（用于数据库初始化）..." -ForegroundColor Yellow
    docker compose build lewis-api
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ 镜像构建失败" -ForegroundColor Red
        exit 1
    }
}

Write-Host "✓ 应用镜像已就绪" -ForegroundColor Green
Write-Host ""

# 执行数据库初始化
Write-Host "🧱 执行数据库表结构初始化..." -ForegroundColor Yellow
Write-Host ""

docker compose run --rm -e SKIP_ENTRYPOINT_DB_INIT=1 lewis-api python3 -m lewis_ai_system.cli init-db

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "✗ 数据库初始化失败" -ForegroundColor Red
    Write-Host "查看日志: docker compose logs postgres" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ 数据库表结构初始化完成" -ForegroundColor Green
Write-Host ""

# 执行种子数据创建
Write-Host "🌱 创建种子数据（测试用户和示例项目）..." -ForegroundColor Yellow
Write-Host ""

docker compose run --rm -e SKIP_ENTRYPOINT_DB_INIT=1 lewis-api python3 scripts/seed_data.py

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "⚠️  种子数据创建失败（非致命错误）" -ForegroundColor Yellow
} else {
    Write-Host "✓ 种子数据创建完成" -ForegroundColor Green
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  ✅ 数据库初始化成功！" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "📝 数据库已准备就绪，可以启动应用服务" -ForegroundColor Cyan
Write-Host ""

