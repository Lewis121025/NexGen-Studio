# Lewis AI System - Docker 完整功能演示脚本
# 使用 Docker Compose 启动所有服务

Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Lewis AI System - Docker 演示启动" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# 检查 .env 文件
if (-not (Test-Path ".env")) {
    Write-Host "✗ .env 文件不存在！" -ForegroundColor Red
    Write-Host "正在从 .env.example 创建..." -ForegroundColor Yellow
    
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "✓ 已创建 .env 文件，请编辑并配置必要的 API 密钥" -ForegroundColor Yellow
        Write-Host "  至少需要配置: OPENROUTER_API_KEY, E2B_API_KEY" -ForegroundColor Yellow
        exit 1
    } else {
        Write-Host "✗ .env.example 也不存在，无法继续" -ForegroundColor Red
        exit 1
    }
}

Write-Host "✓ 配置文件检查通过" -ForegroundColor Green

# 检查 Docker
Write-Host "🔍 检查 Docker 环境..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version 2>&1
    Write-Host "✓ $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Docker 未安装或未启动" -ForegroundColor Red
    Write-Host "请先启动 Docker Desktop" -ForegroundColor Yellow
    exit 1
}

# 检查 Docker Compose
try {
    $composeVersion = docker compose version 2>&1
    Write-Host "✓ $composeVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Docker Compose 不可用" -ForegroundColor Red
    exit 1
}

# 检查 Docker 是否运行
Write-Host "🔍 检查 Docker 守护进程..." -ForegroundColor Yellow
$dockerReady = $false
$maxDockerRetries = 30
$dockerRetryCount = 0

while ($dockerRetryCount -lt $maxDockerRetries) {
    try {
        docker ps | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $dockerReady = $true
            break
        }
    } catch {
        # 继续重试
    }
    $dockerRetryCount++
    if ($dockerRetryCount -eq 1) {
        Write-Host "  Docker 守护进程未运行，等待启动..." -ForegroundColor Yellow
        Write-Host "  如果 Docker Desktop 未启动，请先启动它" -ForegroundColor Gray
    }
    Start-Sleep -Seconds 2
    Write-Host -NoNewline "."
}

Write-Host ""

if (-not $dockerReady) {
    Write-Host "✗ Docker 守护进程未运行" -ForegroundColor Red
    Write-Host ""
    Write-Host "请执行以下步骤:" -ForegroundColor Yellow
    Write-Host "  1. 启动 Docker Desktop 应用程序" -ForegroundColor White
    Write-Host "  2. 等待 Docker Desktop 完全启动（系统托盘图标不再闪烁）" -ForegroundColor White
    Write-Host "  3. 再次运行此脚本: .\demo-docker.ps1" -ForegroundColor White
    Write-Host ""
    exit 1
}

Write-Host "✓ Docker 守护进程正在运行" -ForegroundColor Green

Write-Host ""

# 读取环境变量检查配置
$envContent = Get-Content .env -Raw

# 检查关键配置
$warnings = @()
if ($envContent -notmatch '(?m)^OPENROUTER_API_KEY\s*=\s*sk-or-v1-') {
    $warnings += "OPENROUTER_API_KEY 未配置或无效（某些功能可能受限）"
}

if ($envContent -notmatch '(?m)^E2B_API_KEY\s*=\s*e2b_') {
    $warnings += "E2B_API_KEY 未配置或无效（代码执行功能将不可用）"
}

if ($warnings.Count -gt 0) {
    Write-Host "⚠ 配置警告:" -ForegroundColor Yellow
    foreach ($warning in $warnings) {
        Write-Host "  • $warning" -ForegroundColor Yellow
    }
    Write-Host ""
}

# 自动生成缺失的密钥
$modified = $false

if ($envContent -match 'your_secret_key_here|replace_me_with_secure_hex') {
    Write-Host "🔐 生成 SECRET_KEY..." -ForegroundColor Yellow
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RNGCryptoServiceProvider]::Create().GetBytes($bytes)
    $SECRET_KEY = ($bytes | ForEach-Object { $_.ToString("x2") }) -join ''
    $envContent = $envContent -replace 'your_secret_key_here|replace_me_with_secure_hex', $SECRET_KEY
    $modified = $true
    Write-Host "✓ SECRET_KEY 已生成" -ForegroundColor Green
}

if ($envContent -match 'your_api_key_salt_here') {
    Write-Host "🔐 生成 API_KEY_SALT..." -ForegroundColor Yellow
    $bytes = New-Object byte[] 16
    [System.Security.Cryptography.RNGCryptoServiceProvider]::Create().GetBytes($bytes)
    $API_KEY_SALT = ($bytes | ForEach-Object { $_.ToString("x2") }) -join ''
    $envContent = $envContent -replace 'your_api_key_salt_here', $API_KEY_SALT
    $modified = $true
    Write-Host "✓ API_KEY_SALT 已生成" -ForegroundColor Green
}

if ($modified) {
    Set-Content .env $envContent -NoNewline
    Write-Host "✓ 配置文件已更新" -ForegroundColor Green
    Write-Host ""
}

# 停止现有容器
Write-Host "🛑 停止现有容器..." -ForegroundColor Yellow
docker compose down 2>$null | Out-Null
Write-Host "✓ 已清理旧容器" -ForegroundColor Green

# 构建镜像
Write-Host ""
Write-Host "🏗️ 构建 Docker 镜像..." -ForegroundColor Yellow
Write-Host "  这可能需要几分钟时间..." -ForegroundColor Gray
docker compose build

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ 镜像构建失败" -ForegroundColor Red
    Write-Host "查看详细错误: docker compose build" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ 镜像构建完成" -ForegroundColor Green
Write-Host ""

# 启动数据库服务
Write-Host "🗄️ 启动数据库服务..." -ForegroundColor Yellow
Write-Host "  • PostgreSQL (端口 5432)" -ForegroundColor Gray
Write-Host "  • Redis (端口 6379)" -ForegroundColor Gray
Write-Host "  • Weaviate (端口 8080)" -ForegroundColor Gray

docker compose up -d postgres redis weaviate

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ 数据库服务启动失败" -ForegroundColor Red
    exit 1
}

# 等待数据库就绪
Write-Host "⏳ 等待数据库服务就绪..." -ForegroundColor Yellow
$maxRetries = 60
$retryCount = 0
$postgresReady = $false
$redisReady = $false

while ($retryCount -lt $maxRetries) {
    # 检查 PostgreSQL
    if (-not $postgresReady) {
        try {
            $result = docker compose exec -T postgres pg_isready -U lewis 2>&1
            if ($LASTEXITCODE -eq 0) {
                $postgresReady = $true
                Write-Host "  ✓ PostgreSQL 已就绪" -ForegroundColor Green
            }
        } catch {
            # 继续等待
        }
    }
    
    # 检查 Redis
    if (-not $redisReady) {
        try {
            $result = docker compose exec -T redis redis-cli ping 2>&1
            if ($result -match "PONG") {
                $redisReady = $true
                Write-Host "  ✓ Redis 已就绪" -ForegroundColor Green
            }
        } catch {
            # 继续等待
        }
    }
    
    if ($postgresReady -and $redisReady) {
        break
    }
    
    $retryCount++
    Start-Sleep -Seconds 1
    Write-Host -NoNewline "."
}

Write-Host ""

if (-not $postgresReady) {
    Write-Host "✗ PostgreSQL 未能在预期时间内就绪" -ForegroundColor Red
    Write-Host "查看日志: docker compose logs postgres" -ForegroundColor Yellow
    exit 1
}

if (-not $redisReady) {
    Write-Host "⚠ Redis 未能在预期时间内就绪，但继续执行" -ForegroundColor Yellow
}

Write-Host "✓ 数据库服务已就绪" -ForegroundColor Green
Write-Host ""

# 初始化数据库
Write-Host "🧱 初始化数据库..." -ForegroundColor Yellow
docker compose run --rm -e SKIP_ENTRYPOINT_DB_INIT=1 lewis-api python3 -m lewis_ai_system.cli init-db

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ 数据库初始化失败" -ForegroundColor Red
    Write-Host "查看日志: docker compose logs postgres lewis-api" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ 数据库初始化完成" -ForegroundColor Green
Write-Host ""

# 创建种子数据（如果存在脚本）
if (Test-Path "scripts/seed_data.py") {
    Write-Host "🌱 创建种子数据..." -ForegroundColor Yellow
    docker compose run --rm -e SKIP_ENTRYPOINT_DB_INIT=1 lewis-api python3 scripts/seed_data.py 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ 种子数据创建完成" -ForegroundColor Green
    } else {
        Write-Host "⚠ 种子数据创建失败（非致命错误）" -ForegroundColor Yellow
    }
    Write-Host ""
}

# 启动所有服务
Write-Host "🚀 启动所有服务..." -ForegroundColor Yellow
docker compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ 服务启动失败" -ForegroundColor Red
    Write-Host "查看日志: docker compose logs" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ 所有服务已启动" -ForegroundColor Green
Write-Host ""

# 等待服务就绪
Write-Host "⏳ 等待服务就绪..." -ForegroundColor Yellow
$maxRetries = 60
$retryCount = 0
$apiReady = $false
$frontendReady = $false

while ($retryCount -lt $maxRetries) {
    # 检查后端 API
    if (-not $apiReady) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8000/healthz" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                $apiReady = $true
                Write-Host "  ✓ 后端 API 已就绪" -ForegroundColor Green
            }
        } catch {
            # 继续等待
        }
    }
    
    # 检查前端
    if (-not $frontendReady) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                $frontendReady = $true
                Write-Host "  ✓ 前端服务已就绪" -ForegroundColor Green
            }
        } catch {
            # 继续等待
        }
    }
    
    if ($apiReady -and $frontendReady) {
        break
    }
    
    $retryCount++
    Start-Sleep -Seconds 1
    Write-Host -NoNewline "."
}

Write-Host ""

if (-not $apiReady) {
    Write-Host "⚠ 后端 API 可能未完全就绪" -ForegroundColor Yellow
    Write-Host "查看日志: docker compose logs lewis-api" -ForegroundColor Yellow
}

if (-not $frontendReady) {
    Write-Host "⚠ 前端服务可能未完全就绪" -ForegroundColor Yellow
    Write-Host "查看日志: docker compose logs frontend" -ForegroundColor Yellow
}

Write-Host ""

# 显示服务状态
Write-Host "📊 服务状态:" -ForegroundColor Cyan
docker compose ps
Write-Host ""

# 显示服务信息
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  ✅ Docker 演示环境已就绪！" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 服务地址:" -ForegroundColor Cyan
Write-Host "  • 前端界面: http://localhost:3000" -ForegroundColor White
Write-Host "  • 后端 API: http://localhost:8000" -ForegroundColor White
Write-Host "  • API 文档: http://localhost:8000/docs" -ForegroundColor White
Write-Host "  • 健康检查: http://localhost:8000/healthz" -ForegroundColor White
Write-Host "  • API 版本: http://localhost:8000/api/versions" -ForegroundColor White
Write-Host ""
Write-Host "📝 功能演示:" -ForegroundColor Cyan
Write-Host "  1. 访问前端界面体验完整功能" -ForegroundColor Gray
Write-Host "  2. 使用 API 文档测试后端接口" -ForegroundColor Gray
Write-Host "  3. 创建创意项目或通用会话" -ForegroundColor Gray
Write-Host "  4. 体验 AI 工具调用和代码执行" -ForegroundColor Gray
Write-Host ""
Write-Host "🛑 停止服务:" -ForegroundColor Cyan
Write-Host "  docker compose down        # 停止所有服务" -ForegroundColor Gray
Write-Host "  docker compose stop       # 暂停服务（保留数据）" -ForegroundColor Gray
Write-Host ""
Write-Host "📊 查看日志:" -ForegroundColor Cyan
Write-Host "  docker compose logs -f              # 查看所有服务日志" -ForegroundColor Gray
Write-Host "  docker compose logs -f lewis-api    # 仅查看后端日志" -ForegroundColor Gray
Write-Host "  docker compose logs -f frontend     # 仅查看前端日志" -ForegroundColor Gray
Write-Host ""
Write-Host "🔧 常用命令:" -ForegroundColor Cyan
Write-Host "  docker compose ps          # 查看服务状态" -ForegroundColor Gray
Write-Host "  docker compose restart    # 重启所有服务" -ForegroundColor Gray
Write-Host "  docker compose exec lewis-api bash  # 进入后端容器" -ForegroundColor Gray
Write-Host ""

# 询问是否打开浏览器
$openBrowser = Read-Host "是否在浏览器中打开服务? (Y/n)"
if ($openBrowser -ne 'n' -and $openBrowser -ne 'N') {
    if ($frontendReady) {
        Start-Process "http://localhost:3000"
    }
    Start-Sleep -Seconds 1
    Start-Process "http://localhost:8000/docs"
}

Write-Host ""
Write-Host "✨ 演示环境已准备就绪，祝您使用愉快！" -ForegroundColor Green
Write-Host ""

