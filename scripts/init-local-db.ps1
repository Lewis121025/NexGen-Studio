# Lewis AI System - 本地数据库初始化脚本
# 初始化PostgreSQL数据库结构和种子数据

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[ERR ] $msg" -ForegroundColor Red }
function Write-Success($msg) { Write-Host "[SUCCESS] $msg" -ForegroundColor Green }

Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Lewis AI System - 本地数据库初始化" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# 检查.env文件
if (-not (Test-Path ".env")) {
    Write-Err ".env 文件不存在！"
    Write-Host "请先运行 '.\scripts\start-local-databases.ps1' 创建配置" -ForegroundColor Yellow
    exit 1
}

Write-Success "✓ 找到 .env 配置文件"

# 检查Python环境
Write-Host ""
Write-Host "🐍 检查Python环境..." -ForegroundColor Yellow

try {
    $pythonVersion = python3 --version 2>&1
    Write-Success "✓ $pythonVersion"
} catch {
    Write-Err "Python未安装或未添加到PATH"
    Write-Host "请安装Python 3.11+并确保可以正常运行" -ForegroundColor Yellow
    exit 1
}

# 检查项目依赖
Write-Host ""
Write-Host "📦 检查项目依赖..." -ForegroundColor Yellow

$hasPackage = python3 -c "import lewis_ai_system" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Info "安装项目依赖..."
    python3 -m pip install -e .
    if ($LASTEXITCODE -ne 0) {
        Write-Err "依赖安装失败"
        exit 1
    }
}
Write-Success "✓ 项目依赖已安装"

# 解析数据库连接信息
Write-Host ""
Write-Host "🔍 解析数据库配置..." -ForegroundColor Yellow

$envContent = Get-Content ".env" -Raw
$dbUrl = ($envContent -match "DATABASE_URL=(.+)" | ForEach-Object { $matches[1] }) | Select-Object -First 1

if (-not $dbUrl) {
    Write-Err "DATABASE_URL 未配置"
    exit 1
}

Write-Success "✓ 数据库连接字符串已配置"

# 测试数据库连接
Write-Host ""
Write-Host "🔗 测试数据库连接..." -ForegroundColor Yellow

$connectionString = $dbUrl -replace "postgresql\+asyncpg://", ""
$userPart = $connectionString.Split("@")[0]
$user = $userPart.Split(":")[0]
$password = $userPart.Split(":")[1]
$hostPortDb = $connectionString.Split("@")[1]
$host = $hostPortDb.Split("/")[0].Split(":")[0]
$port = $hostPortDb.Split("/")[0].Split(":")[1]
$database = $hostPortDb.Split("/")[1]

$connectionTest = python3 -c "
import asyncio
import asyncpg
import sys

async def test_connection():
    try:
        conn = await asyncpg.connect('$dbUrl')
        await conn.execute('SELECT 1')
        await conn.close()
        print('Database connection successful')
        sys.exit(0)
    except Exception as e:
        print(f'Database connection failed: {e}')
        sys.exit(1)

asyncio.run(test_connection())
" 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Err "数据库连接失败"
    Write-Host "请检查:" -ForegroundColor Yellow
    Write-Host "  1. PostgreSQL服务是否正在运行" -ForegroundColor Gray
    Write-Host "  2. .env中的DATABASE_URL是否正确" -ForegroundColor Gray
    Write-Host "  3. 数据库用户和密码是否正确" -ForegroundColor Gray
    exit 1
}

Write-Success "✓ 数据库连接成功"

# 执行数据库初始化
Write-Host ""
Write-Host "🧱 执行数据库表结构初始化..." -ForegroundColor Yellow

$initResult = python3 -m lewis_ai_system.cli init-db 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Err "数据库初始化失败"
    Write-Host "错误信息: $initResult" -ForegroundColor Red
    exit 1
}

Write-Success "✓ 数据库表结构初始化完成"

# 执行种子数据创建
Write-Host ""
Write-Host "🌱 创建种子数据..." -ForegroundColor Yellow

if (Test-Path "scripts\seed_data.py") {
    $seedResult = python scripts\seed_data.py 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "种子数据创建失败（非致命错误）"
        Write-Host "错误信息: $seedResult" -ForegroundColor Yellow
    } else {
        Write-Success "✓ 种子数据创建完成"
    }
} else {
    Write-Warn "未找到种子数据脚本"
}

# 验证数据库结构
Write-Host ""
Write-Host "✅ 验证数据库结构..." -ForegroundColor Yellow

$validationResult = python3 -c "
import asyncio
import asyncpg
import sys

async def validate_schema():
    try:
        conn = await asyncpg.connect('$dbUrl')
        
        # 检查核心表是否存在
        tables = [
            'users',
            'creative_projects', 
            'general_sessions',
            'agent_executions',
            'cost_records'
        ]
        
        for table in tables:
            result = await conn.fetchval(\"SELECT to_regclass('$table')\")
            if result:
                print(f'✓ 表 {table} 存在')
            else:
                print(f'✗ 表 {table} 不存在')
                sys.exit(1)
        
        await conn.close()
        print('数据库结构验证成功')
        sys.exit(0)
    except Exception as e:
        print(f'验证失败: {e}')
        sys.exit(1)

asyncio.run(validate_schema())
" 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Err "数据库结构验证失败"
    exit 1
}

Write-Success "✓ 数据库结构验证通过"

# ==============================================
# 完成总结
# ==============================================
Write-Host ""
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  ✅ 本地数据库初始化完成！" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""

Write-Host "📊 数据库信息:" -ForegroundColor Cyan
Write-Host "  主机: $host`:$port" -ForegroundColor Gray
Write-Host "  数据库: $database" -ForegroundColor Gray
Write-Host "  用户: $user" -ForegroundColor Gray

Write-Host ""
Write-Host "📝 下一步操作:" -ForegroundColor Cyan
Write-Host "  1. 运行 '.\scripts\start-local-app.ps1' 启动应用服务" -ForegroundColor Gray
Write-Host "  2. 访问 http://localhost:3000 查看前端" -ForegroundColor Gray
Write-Host "  3. 访问 http://localhost:8000/docs 查看API文档" -ForegroundColor Gray

Write-Host ""
Write-Host "🔧 常用查询:" -ForegroundColor Cyan
Write-Host "  连接数据库: sqlcmd -S $host,$port -U $user -d $database" -ForegroundColor Gray
Write-Host "  查看表:     python -c \"import asyncio; import asyncpg; print(asyncio.run(asyncpg.connect('$dbUrl').fetch('SELECT tablename FROM pg_tables WHERE schemaname=\\'public\\'')))\"" -ForegroundColor Gray

Write-Host ""

