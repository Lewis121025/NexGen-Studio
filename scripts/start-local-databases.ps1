# Lewis AI System - 本地数据库服务启动脚本
# 使用本地安装的PostgreSQL、Redis和Weaviate

param(
    [switch]$SkipWeaviate = $false,
    [int]$WeaviatePort = 8080
)

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[ERR ] $msg" -ForegroundColor Red }
function Write-Success($msg) { Write-Host "[SUCCESS] $msg" -ForegroundColor Green }

Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Lewis AI System - 本地数据库服务启动" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# 检查.env文件
if (-not (Test-Path ".env")) {
    Write-Host "⚠️ .env 文件不存在！" -ForegroundColor Yellow
    Write-Host "正在从模板创建 .env 文件..." -ForegroundColor Cyan
    
    if (Test-Path ".env.local.example") {
        Copy-Item ".env.local.example" ".env"
        Write-Success "✓ 已从 .env.local.example 创建 .env 文件"
        Write-Host "请编辑 .env 文件并根据您的本地配置调整数据库连接信息" -ForegroundColor Yellow
    } else {
        Write-Err "找不到 .env.local.example 模板文件"
        exit 1
    }
} else {
    Write-Success "✓ 发现 .env 配置文件"
}

# 检查必要的数据库配置
Write-Host ""
Write-Host "🔍 检查数据库配置..." -ForegroundColor Yellow

$envContent = Get-Content ".env" -Raw
$dbUrl = ($envContent -match "DATABASE_URL=(.+)" | ForEach-Object { $matches[1] }) | Select-Object -First 1
$redisUrl = ($envContent -match "REDIS_URL=(.+)" | ForEach-Object { $matches[1] }) | Select-Object -First 1

if (-not $dbUrl) {
    Write-Err "DATABASE_URL 未在 .env 中配置"
    exit 1
}

if (-not $redisUrl) {
    Write-Err "REDIS_URL 未在 .env 中配置"
    exit 1
}

Write-Success "✓ 数据库URL配置正确"
Write-Host "  数据库: $dbUrl" -ForegroundColor Gray
Write-Host "  Redis: $redisUrl" -ForegroundColor Gray

# ==============================================
# 启动PostgreSQL
# ==============================================
Write-Host ""
Write-Host "🗄️ 检查PostgreSQL服务..." -ForegroundColor Yellow

$pgServiceName = "postgresql-x64-15"  # PostgreSQL 15 服务名称模式
$serviceFound = $false

try {
    $service = Get-Service -Name $pgServiceName -ErrorAction SilentlyContinue
    if ($service) {
        $serviceFound = $true
        if ($service.Status -ne "Running") {
            Write-Info "启动PostgreSQL服务..."
            Start-Service -Name $pgServiceName
            Start-Sleep -Seconds 3
        }
        Write-Success "✓ PostgreSQL服务正在运行"
    }
} catch {
    Write-Warn "无法找到PostgreSQL服务 '$pgServiceName'"
    Write-Host "请确保PostgreSQL已安装并以服务形式运行" -ForegroundColor Yellow
}

# 尝试检查PostgreSQL连接
if ($serviceFound) {
    $maxRetries = 10
    $retryCount = 0
    $pgReady = $false

    while ($retryCount -lt $maxRetries) {
        try {
            $connectionString = $dbUrl -replace "postgresql\+asyncpg://", ""
            $userPart = $connectionString.Split("@")[0]
            $user = $userPart.Split(":")[0]
            $password = $userPart.Split(":")[1]
            $hostPortDb = $connectionString.Split("@")[1]
            $host = $hostPortDb.Split("/")[0].Split(":")[0]
            $port = $hostPortDb.Split("/")[0].Split(":")[1]
            $database = $hostPortDb.Split("/")[1]

            # 使用sqlcmd检查连接
            $result = sqlcmd -S "$host,$port" -U $user -P $password -Q "SELECT 1" -d $database -h -1 2>&1
            if ($LASTEXITCODE -eq 0) {
                $pgReady = $true
                break
            }
        } catch {
            # 继续重试
        }
        $retryCount++
        Start-Sleep -Seconds 1
    }

    if ($pgReady) {
        Write-Success "✓ PostgreSQL连接测试成功"
    } else {
        Write-Warn "⚠ 无法连接到PostgreSQL，但服务可能正在启动中"
    }
}

# ==============================================
# 启动Redis
# ==============================================
Write-Host ""
Write-Host "🔴 检查Redis服务..." -ForegroundColor Yellow

$redisServiceName = "Redis"
$redisFound = $false

try {
    $service = Get-Service -Name $redisServiceName -ErrorAction SilentlyContinue
    if ($service) {
        $redisFound = $true
        if ($service.Status -ne "Running") {
            Write-Info "启动Redis服务..."
            Start-Service -Name $redisServiceName
            Start-Sleep -Seconds 2
        }
        Write-Success "✓ Redis服务正在运行"
    }
} catch {
    Write-Warn "无法找到Redis服务 '$redisServiceName'"
}

# 尝试Redis连接测试
if ($redisFound) {
    try {
        # 尝试使用redis-cli ping
        $result = redis-cli ping 2>&1
        if ($result -match "PONG") {
            Write-Success "✓ Redis连接测试成功"
        } else {
            Write-Warn "⚠ Redis可能正在启动中"
        }
    } catch {
        Write-Warn "⚠ 无法测试Redis连接（redis-cli可能未安装）"
    }
}

# ==============================================
# 启动Weaviate（可选）
# ==============================================
if (-not $SkipWeaviate) {
    Write-Host ""
    Write-Host "📊 检查Weaviate服务..." -ForegroundColor Yellow
    
    $weaviatePort = $WeaviatePort
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$weaviatePort/v1/schema" -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Success "✓ Weaviate服务正在运行"
        }
    } catch {
        Write-Warn "⚠ Weaviate服务未运行或无法连接"
        Write-Host "如果您需要向量数据库功能，请启动Weaviate服务" -ForegroundColor Yellow
        Write-Host "Weaviate下载: https://github.com/weaviate/weaviate/releases" -ForegroundColor Gray
        Write-Host "或者使用Docker启动: docker run -d -p $weaviatePort`:8080 semitechnologies/weaviate" -ForegroundColor Gray
    }
} else {
    Write-Host ""
    Write-Host "⏭️ 跳过Weaviate检查（根据参数设置）" -ForegroundColor Gray
}

# ==============================================
# 总结
# ==============================================
Write-Host ""
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  数据库服务检查完成" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""

Write-Host "📋 服务状态总结:" -ForegroundColor Cyan
Write-Host "  PostgreSQL: $(if ($serviceFound) { '✓ 正在运行' } else { '⚠ 未检测到服务' })" -ForegroundColor $(if ($serviceFound) { 'Green' } else { 'Yellow' })
Write-Host "  Redis:      $(if ($redisFound) { '✓ 正在运行' } else { '⚠ 未检测到服务' })" -ForegroundColor $(if ($redisFound) { 'Green' } else { 'Yellow' })
Write-Host "  Weaviate:   $(if (-not $SkipWeaviate) { '⏭️ 跳过检查' } else { '⏭️ 跳过检查' })" -ForegroundColor Gray

Write-Host ""
Write-Host "📝 下一步操作:" -ForegroundColor Cyan
Write-Host "  1. 如果服务未运行，请手动启动相应的数据库服务" -ForegroundColor Gray
Write-Host "  2. 运行 '.\scripts\init-local-db.ps1' 初始化数据库结构" -ForegroundColor Gray
Write-Host "  3. 运行 '.\scripts\start-local-app.ps1' 启动应用服务" -ForegroundColor Gray

Write-Host ""
Write-Host "🔧 常用命令:" -ForegroundColor Cyan
Write-Host "  启动PostgreSQL: net start postgresql-x64-15" -ForegroundColor Gray
Write-Host "  启动Redis:      net start Redis" -ForegroundColor Gray
Write-Host "  查看PostgreSQL: sqlcmd -S localhost,5432 -U lewis" -ForegroundColor Gray
Write-Host "  测试Redis:      redis-cli ping" -ForegroundColor Gray

Write-Host ""

