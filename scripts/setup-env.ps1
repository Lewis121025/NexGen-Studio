# Lewis AI System - 快速配置脚本
# 自动完成环境初始化

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host "=" * 69 -ForegroundColor Cyan
Write-Host "  Lewis AI System - 环境配置向导" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

# 1. 检查 Python 版本
Write-Host "[1/6] 检查 Python 版本..." -ForegroundColor Yellow
$pythonVersion = python3 --version 2>&1
if ($pythonVersion -match "Python 3\.(1[1-9]|[2-9]\d)") {
    Write-Host "  ✓ Python 版本: $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "  ✗ 需要 Python 3.11+, 当前: $pythonVersion" -ForegroundColor Red
    exit 1
}

# 2. 创建 .env 文件
Write-Host ""
Write-Host "[2/6] 配置环境变量..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host "  ⚠ .env 文件已存在,跳过" -ForegroundColor Yellow
} else {
    Copy-Item ".env.example" ".env"
    Write-Host "  ✓ 已创建 .env 文件 (从 .env.example 复制)" -ForegroundColor Green
    Write-Host "  ⚠ 请编辑 .env 文件并填写真实的 API Keys!" -ForegroundColor Yellow
}

# 3. 安装 Python 依赖
Write-Host ""
Write-Host "[3/6] 安装 Python 依赖..." -ForegroundColor Yellow
Write-Host "  正在安装..." -ForegroundColor Gray
pip install -e . --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Python 依赖安装完成" -ForegroundColor Green
} else {
    Write-Host "  ✗ 依赖安装失败" -ForegroundColor Red
    exit 1
}

# 4. 检查 Docker
Write-Host ""
Write-Host "[4/6] 检查 Docker..." -ForegroundColor Yellow
$dockerVersion = docker --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Docker 版本: $dockerVersion" -ForegroundColor Green
} else {
    Write-Host "  ✗ Docker 未安装或未启动" -ForegroundColor Red
    Write-Host "  请安装 Docker Desktop: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    exit 1
}

# 5. 启动数据库服务
Write-Host ""
Write-Host "[5/6] 启动数据库服务..." -ForegroundColor Yellow
Write-Host "  正在启动 PostgreSQL, Redis, Weaviate..." -ForegroundColor Gray
docker compose up -d postgres redis weaviate 2>&1 | Out-Null
Start-Sleep -Seconds 5  # 等待服务启动

# 检查服务状态
$services = docker compose ps postgres redis weaviate --format json | ConvertFrom-Json
$allRunning = $true
foreach ($service in $services) {
    if ($service.State -ne "running") {
        $allRunning = $false
        Write-Host "  ✗ $($service.Service) 未运行" -ForegroundColor Red
    }
}

if ($allRunning) {
    Write-Host "  ✓ 数据库服务已启动" -ForegroundColor Green
} else {
    Write-Host "  ⚠ 部分服务未启动,请检查 Docker 日志" -ForegroundColor Yellow
}

# 6. 初始化数据库
Write-Host ""
Write-Host "[6/6] 初始化数据库..." -ForegroundColor Yellow
Write-Host "  等待数据库就绪..." -ForegroundColor Gray
Start-Sleep -Seconds 3

Write-Host "  运行数据库迁移..." -ForegroundColor Gray
alembic upgrade head 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ 数据库迁移完成" -ForegroundColor Green
} else {
    Write-Host "  ⚠ 数据库迁移失败 (可能是首次运行)" -ForegroundColor Yellow
    Write-Host "  请手动运行: alembic upgrade head" -ForegroundColor Yellow
}

# 完成
Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "  ✅ 环境配置完成!" -ForegroundColor Green
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

Write-Host "下一步操作:" -ForegroundColor Yellow
Write-Host "  1. 编辑 .env 文件,填写真实的 API Keys" -ForegroundColor White
Write-Host "     必需: OPENROUTER_API_KEY, E2B_API_KEY" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. 运行自检脚本:" -ForegroundColor White
Write-Host "     python production_check.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "  3. 启动服务:" -ForegroundColor White
Write-Host "     docker compose up -d" -ForegroundColor Cyan
Write-Host ""
Write-Host "  4. 访问应用:" -ForegroundColor White
Write-Host "     前端: http://localhost:3000" -ForegroundColor Cyan
Write-Host "     后端: http://localhost:8000" -ForegroundColor Cyan
Write-Host "     API文档: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
