# Lewis AI System - 本地服务安装与配置指南
# 此脚本帮助您在本地安装和配置所需的数据库服务（无Docker）

param(
    [switch]$InstallPostgres = $false,
    [switch]$InstallRedis = $false,
    [switch]$InstallWeaviate = $false,
    [switch]$InstallAll = $false,
    [switch]$CheckOnly = $false
)

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[ERR ] $msg" -ForegroundColor Red }
function Write-Success($msg) { Write-Host "[OK  ] $msg" -ForegroundColor Green }

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     Lewis AI System - 本地服务安装与配置                      ║" -ForegroundColor Cyan
Write-Host "║     完全本地运行，无需Docker                                   ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

if ($InstallAll) {
    $InstallPostgres = $true
    $InstallRedis = $true
    $InstallWeaviate = $true
}

# ==============================================
# 检查 Chocolatey（Windows 包管理器）
# ==============================================
Write-Host "🔍 检查包管理器..." -ForegroundColor Yellow

$chocoInstalled = $false
try {
    $chocoVersion = choco --version 2>$null
    if ($chocoVersion) {
        $chocoInstalled = $true
        Write-Success "✓ Chocolatey 已安装 (v$chocoVersion)"
    }
} catch {
    Write-Warn "⚠ Chocolatey 未安装"
}

$wingetInstalled = $false
try {
    $wingetVersion = winget --version 2>$null
    if ($wingetVersion) {
        $wingetInstalled = $true
        Write-Success "✓ Winget 已安装 ($wingetVersion)"
    }
} catch {
    Write-Warn "⚠ Winget 未安装"
}

if (-not $chocoInstalled -and -not $wingetInstalled) {
    Write-Host ""
    Write-Host "📦 建议安装 Chocolatey 或 Winget 以便自动安装依赖" -ForegroundColor Yellow
    Write-Host "   Chocolatey: https://chocolatey.org/install" -ForegroundColor Gray
    Write-Host "   Winget: 通常随 Windows 11 或 App Installer 一起安装" -ForegroundColor Gray
}

# ==============================================
# 检查/安装 PostgreSQL
# ==============================================
Write-Host ""
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  PostgreSQL 数据库" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan

$postgresInstalled = $false
$postgresRunning = $false

# 检查 PostgreSQL 服务
$pgServices = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue
if ($pgServices) {
    $postgresInstalled = $true
    $runningService = $pgServices | Where-Object { $_.Status -eq "Running" } | Select-Object -First 1
    if ($runningService) {
        $postgresRunning = $true
        Write-Success "✓ PostgreSQL 服务正在运行: $($runningService.Name)"
    } else {
        Write-Warn "⚠ PostgreSQL 已安装但未运行"
        Write-Host "  服务名称: $($pgServices[0].Name)" -ForegroundColor Gray
    }
}

# 检查 psql 命令
try {
    $psqlVersion = psql --version 2>$null
    if ($psqlVersion) {
        Write-Success "✓ psql 命令可用: $psqlVersion"
    }
} catch {
    if ($postgresInstalled) {
        Write-Warn "⚠ psql 命令不在 PATH 中，可能需要手动添加"
    }
}

if (-not $postgresInstalled) {
    Write-Warn "✗ PostgreSQL 未安装"
    
    if ($InstallPostgres -and -not $CheckOnly) {
        Write-Host ""
        Write-Info "正在安装 PostgreSQL..."
        
        if ($chocoInstalled) {
            Write-Info "使用 Chocolatey 安装..."
            choco install postgresql15 -y
        } elseif ($wingetInstalled) {
            Write-Info "使用 Winget 安装..."
            winget install PostgreSQL.PostgreSQL.15 --silent
        } else {
            Write-Host ""
            Write-Host "📥 请手动下载并安装 PostgreSQL:" -ForegroundColor Yellow
            Write-Host "   下载地址: https://www.postgresql.org/download/windows/" -ForegroundColor Gray
            Write-Host "   推荐版本: PostgreSQL 15.x" -ForegroundColor Gray
            Write-Host ""
            Write-Host "   安装时请记住设置的密码，并在 .env 中更新 DATABASE_URL" -ForegroundColor Yellow
        }
    } else {
        Write-Host ""
        Write-Host "📥 PostgreSQL 安装方法:" -ForegroundColor Yellow
        Write-Host "   方法1 (Chocolatey): choco install postgresql15 -y" -ForegroundColor Gray
        Write-Host "   方法2 (Winget):     winget install PostgreSQL.PostgreSQL.15" -ForegroundColor Gray
        Write-Host "   方法3 (手动):       https://www.postgresql.org/download/windows/" -ForegroundColor Gray
    }
}

# ==============================================
# 检查/安装 Redis
# ==============================================
Write-Host ""
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Redis 缓存服务" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan

$redisInstalled = $false
$redisRunning = $false

# 检查 Redis 服务
$redisService = Get-Service -Name "Redis" -ErrorAction SilentlyContinue
if ($redisService) {
    $redisInstalled = $true
    if ($redisService.Status -eq "Running") {
        $redisRunning = $true
        Write-Success "✓ Redis 服务正在运行"
    } else {
        Write-Warn "⚠ Redis 已安装但未运行"
    }
}

# 检查 redis-cli 命令
try {
    $redisCliTest = redis-cli --version 2>$null
    if ($redisCliTest) {
        Write-Success "✓ redis-cli 命令可用"
        
        # 尝试 ping
        $pingResult = redis-cli ping 2>$null
        if ($pingResult -eq "PONG") {
            $redisRunning = $true
            Write-Success "✓ Redis 连接正常"
        }
    }
} catch {
    # redis-cli 不可用
}

if (-not $redisInstalled -and -not $redisRunning) {
    Write-Warn "✗ Redis 未安装或未运行"
    
    if ($InstallRedis -and -not $CheckOnly) {
        Write-Host ""
        Write-Info "正在安装 Redis..."
        
        if ($chocoInstalled) {
            Write-Info "使用 Chocolatey 安装..."
            choco install redis-64 -y
        } else {
            Write-Host ""
            Write-Host "📥 请手动下载并安装 Redis for Windows:" -ForegroundColor Yellow
            Write-Host "   下载地址: https://github.com/tporadowski/redis/releases" -ForegroundColor Gray
            Write-Host "   或使用 Memurai (Redis 兼容): https://www.memurai.com/" -ForegroundColor Gray
        }
    } else {
        Write-Host ""
        Write-Host "📥 Redis 安装方法:" -ForegroundColor Yellow
        Write-Host "   方法1 (Chocolatey): choco install redis-64 -y" -ForegroundColor Gray
        Write-Host "   方法2 (手动):       https://github.com/tporadowski/redis/releases" -ForegroundColor Gray
        Write-Host "   方法3 (Memurai):    https://www.memurai.com/ (Windows 原生 Redis 替代)" -ForegroundColor Gray
        Write-Host ""
        Write-Host "💡 如果不想安装 Redis，可以在 .env 中设置 REDIS_ENABLED=false" -ForegroundColor Cyan
        Write-Host "   系统会自动使用内存缓存作为替代" -ForegroundColor Gray
    }
}

# ==============================================
# 检查/安装 Weaviate（向量数据库，可选）
# ==============================================
Write-Host ""
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Weaviate 向量数据库（可选）" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan

$weaviateRunning = $false

try {
    $response = Invoke-WebRequest -Uri "http://localhost:8080/v1/.well-known/ready" -UseBasicParsing -TimeoutSec 3 -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
        $weaviateRunning = $true
        Write-Success "✓ Weaviate 服务正在运行 (http://localhost:8080)"
    }
} catch {
    Write-Warn "⚠ Weaviate 未运行"
}

if (-not $weaviateRunning) {
    Write-Host ""
    Write-Host "📥 Weaviate 是可选的向量数据库，用于语义搜索功能" -ForegroundColor Yellow
    Write-Host "   如果不安装，系统会自动使用内存向量存储" -ForegroundColor Gray
    Write-Host ""
    Write-Host "   安装方法:" -ForegroundColor Yellow
    Write-Host "   1. 下载: https://github.com/weaviate/weaviate/releases" -ForegroundColor Gray
    Write-Host "   2. 解压并运行 weaviate.exe" -ForegroundColor Gray
    Write-Host "   3. 或使用 Docker: docker run -d -p 8080:8080 semitechnologies/weaviate" -ForegroundColor Gray
}

# ==============================================
# 创建数据库和用户
# ==============================================
Write-Host ""
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  数据库配置" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan

if ($postgresRunning -and -not $CheckOnly) {
    Write-Host ""
    Write-Host "📊 检查数据库配置..." -ForegroundColor Yellow
    
    # 读取 .env 获取数据库配置
    if (Test-Path ".env") {
        $envContent = Get-Content ".env" -Raw
        if ($envContent -match "DATABASE_URL=postgresql\+asyncpg://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)") {
            $dbUser = $matches[1]
            $dbPass = $matches[2]
            $dbHost = $matches[3]
            $dbPort = $matches[4]
            $dbName = $matches[5]
            
            Write-Host "  用户: $dbUser" -ForegroundColor Gray
            Write-Host "  主机: $dbHost`:$dbPort" -ForegroundColor Gray
            Write-Host "  数据库: $dbName" -ForegroundColor Gray
            
            Write-Host ""
            Write-Host "💡 如果数据库用户不存在，请使用以下 SQL 命令创建:" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "   -- 以管理员身份连接 PostgreSQL 后执行:" -ForegroundColor Gray
            Write-Host "   CREATE USER $dbUser WITH PASSWORD '$dbPass';" -ForegroundColor White
            Write-Host "   CREATE DATABASE $dbName OWNER $dbUser;" -ForegroundColor White
            Write-Host "   GRANT ALL PRIVILEGES ON DATABASE $dbName TO $dbUser;" -ForegroundColor White
        }
    }
}

# ==============================================
# 总结
# ==============================================
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                      检查完成                                 ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

Write-Host "📋 服务状态总结:" -ForegroundColor Cyan
Write-Host "  ├─ PostgreSQL: $(if ($postgresRunning) { '✓ 运行中' } elseif ($postgresInstalled) { '⚠ 已安装但未运行' } else { '✗ 未安装' })" -ForegroundColor $(if ($postgresRunning) { 'Green' } elseif ($postgresInstalled) { 'Yellow' } else { 'Red' })
Write-Host "  ├─ Redis:      $(if ($redisRunning) { '✓ 运行中' } elseif ($redisInstalled) { '⚠ 已安装但未运行' } else { '✗ 未安装（可用内存缓存替代）' })" -ForegroundColor $(if ($redisRunning) { 'Green' } elseif ($redisInstalled) { 'Yellow' } else { 'Yellow' })
Write-Host "  └─ Weaviate:   $(if ($weaviateRunning) { '✓ 运行中' } else { '⚠ 未运行（可用内存向量库替代）' })" -ForegroundColor $(if ($weaviateRunning) { 'Green' } else { 'Yellow' })

Write-Host ""
Write-Host "📝 下一步操作:" -ForegroundColor Cyan

$nextStep = 1
if (-not $postgresRunning) {
    Write-Host "  $nextStep. 安装并启动 PostgreSQL（必需）" -ForegroundColor Yellow
    $nextStep++
}
if (-not $redisRunning) {
    Write-Host "  $nextStep. 安装并启动 Redis，或在 .env 中设置 REDIS_ENABLED=false" -ForegroundColor Gray
    $nextStep++
}

Write-Host "  $nextStep. 运行 '.\scripts\start-local.ps1' 启动应用" -ForegroundColor Gray

Write-Host ""
Write-Host "🔧 常用命令:" -ForegroundColor Cyan
Write-Host "  启动 PostgreSQL 服务: net start postgresql-x64-15" -ForegroundColor Gray
Write-Host "  启动 Redis 服务:      net start Redis" -ForegroundColor Gray
Write-Host "  初始化数据库:         .\scripts\init-local-db.ps1" -ForegroundColor Gray
Write-Host "  启动应用:             .\scripts\start-local.ps1" -ForegroundColor Gray
Write-Host ""
