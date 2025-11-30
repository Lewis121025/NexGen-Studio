# Lewis AI System - 完整本地启动脚本（无Docker）
# 此脚本启动所有服务：后端API、前端、Worker

param(
    [switch]$SkipFrontend = $false,
    [switch]$SkipWorker = $false,
    [switch]$SkipDatabaseCheck = $false,
    [switch]$InitDatabase = $false,
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000,
    [switch]$OpenBrowser = $true,
    [switch]$Verbose = $false
)

$ErrorActionPreference = "Stop"

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[ERR ] $msg" -ForegroundColor Red }
function Write-Success($msg) { Write-Host "[OK  ] $msg" -ForegroundColor Green }
function Write-Debug($msg) { if ($Verbose) { Write-Host "[DBG ] $msg" -ForegroundColor Gray } }

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     Lewis AI System - 本地启动（无Docker）                    ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ==============================================
# 检查 .env 文件
# ==============================================
if (-not (Test-Path ".env")) {
    Write-Err ".env 文件不存在！"
    Write-Host "请创建 .env 文件并配置必要的环境变量" -ForegroundColor Yellow
    exit 1
}
Write-Success "✓ 找到 .env 配置文件"

# 加载环境变量
Get-Content ".env" | ForEach-Object {
    if ($_ -match "^\s*([^#][^=]+)=(.*)$") {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

# ==============================================
# 检查 Python 环境
# ==============================================
Write-Host ""
Write-Host "🐍 检查 Python 环境..." -ForegroundColor Yellow

try {
    $pythonVersion = python3 --version 2>&1
    Write-Success "✓ $pythonVersion"
} catch {
    Write-Err "Python 未安装或未添加到 PATH"
    exit 1
}

# 检查 Python 依赖
Write-Debug "检查 Python 依赖..."
$hasPackages = python3 -c "import fastapi, uvicorn, sqlalchemy, asyncpg" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Info "安装 Python 依赖..."
    python3 -m pip install -e . --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Python 依赖安装失败"
        exit 1
    }
}
Write-Success "✓ Python 依赖已就绪"

# ==============================================
# 检查数据库服务（可选跳过）
# ==============================================
if (-not $SkipDatabaseCheck) {
    Write-Host ""
    Write-Host "🗄️ 检查数据库服务..." -ForegroundColor Yellow
    
    # 检查 PostgreSQL
    $dbUrl = [Environment]::GetEnvironmentVariable("DATABASE_URL", "Process")
    if ($dbUrl) {
        Write-Debug "测试 PostgreSQL 连接..."
        
        $testScript = @"
import asyncio
import sys
try:
    import asyncpg
    async def test():
        try:
            conn = await asyncpg.connect('$dbUrl', timeout=5)
            await conn.execute('SELECT 1')
            await conn.close()
            return True
        except Exception as e:
            print(f'连接失败: {e}', file=sys.stderr)
            return False
    result = asyncio.run(test())
    sys.exit(0 if result else 1)
except ImportError:
    print('asyncpg 未安装', file=sys.stderr)
    sys.exit(1)
"@
        
        $testResult = python -c $testScript 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "✓ PostgreSQL 连接正常"
        } else {
            Write-Err "PostgreSQL 连接失败"
            Write-Host "  错误: $testResult" -ForegroundColor Red
            Write-Host ""
            Write-Host "请确保:" -ForegroundColor Yellow
            Write-Host "  1. PostgreSQL 服务正在运行" -ForegroundColor Gray
            Write-Host "  2. .env 中的 DATABASE_URL 配置正确" -ForegroundColor Gray
            Write-Host "  3. 数据库用户和密码正确" -ForegroundColor Gray
            Write-Host ""
            Write-Host "运行 '.\scripts\setup-local-services.ps1' 检查服务状态" -ForegroundColor Cyan
            exit 1
        }
    } else {
        Write-Warn "⚠ DATABASE_URL 未配置"
    }
    
    # 检查 Redis（可选）
    $redisEnabled = [Environment]::GetEnvironmentVariable("REDIS_ENABLED", "Process")
    $redisUrl = [Environment]::GetEnvironmentVariable("REDIS_URL", "Process")
    
    if ($redisEnabled -eq "true" -and $redisUrl) {
        Write-Debug "测试 Redis 连接..."
        try {
            $pingResult = redis-cli ping 2>$null
            if ($pingResult -eq "PONG") {
                Write-Success "✓ Redis 连接正常"
            } else {
                Write-Warn "⚠ Redis 未响应，将使用内存缓存"
            }
        } catch {
            Write-Warn "⚠ Redis 不可用，将使用内存缓存"
        }
    } else {
        Write-Info "Redis 已禁用，使用内存缓存"
    }
}

# ==============================================
# 初始化数据库（可选）
# ==============================================
if ($InitDatabase) {
    Write-Host ""
    Write-Host "🧱 初始化数据库..." -ForegroundColor Yellow
    
    python3 -m lewis_ai_system.cli init-db
    if ($LASTEXITCODE -ne 0) {
        Write-Err "数据库初始化失败"
        exit 1
    }
    Write-Success "✓ 数据库初始化完成"
}

# ==============================================
# 检查 Node.js（前端）
# ==============================================
if (-not $SkipFrontend) {
    Write-Host ""
    Write-Host "📦 检查 Node.js 环境..." -ForegroundColor Yellow
    
    try {
        $nodeVersion = node --version 2>&1
        $npmVersion = npm --version 2>&1
        Write-Success "✓ Node.js $nodeVersion, npm $npmVersion"
    } catch {
        Write-Warn "⚠ Node.js 未安装，跳过前端启动"
        $SkipFrontend = $true
    }
    
    if (-not $SkipFrontend -and -not (Test-Path "frontend\package.json")) {
        Write-Warn "⚠ 未找到 frontend/package.json，跳过前端启动"
        $SkipFrontend = $true
    }
    
    if (-not $SkipFrontend -and -not (Test-Path "frontend\node_modules")) {
        Write-Info "安装前端依赖..."
        Push-Location frontend
        npm install --silent
        Pop-Location
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "⚠ 前端依赖安装失败，跳过前端启动"
            $SkipFrontend = $true
        } else {
            Write-Success "✓ 前端依赖已安装"
        }
    }
}

# ==============================================
# 创建日志目录
# ==============================================
if (-not (Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" -Force | Out-Null
}

# ==============================================
# 启动后端 API
# ==============================================
Write-Host ""
Write-Host "🚀 启动后端 API 服务..." -ForegroundColor Yellow

$backendLogFile = "logs\backend.log"

# 创建启动脚本
$backendScript = @"
import uvicorn
if __name__ == "__main__":
    uvicorn.run(
        "lewis_ai_system.main:app",
        host="0.0.0.0",
        port=$BackendPort,
        reload=True,
        log_level="info"
    )
"@

$backendScript | Out-File -FilePath "start_backend.py" -Encoding UTF8

$backendProcess = Start-Process -FilePath "python" -ArgumentList "start_backend.py" `
    -RedirectStandardOutput $backendLogFile `
    -RedirectStandardError "logs\backend_error.log" `
    -PassThru -WindowStyle Hidden

Write-Success "✓ 后端进程已启动 (PID: $($backendProcess.Id))"

# 等待后端启动
Write-Host "⏳ 等待后端服务就绪..." -ForegroundColor Yellow
$maxRetries = 30
$retryCount = 0
$backendReady = $false

while ($retryCount -lt $maxRetries) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$BackendPort/healthz" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $backendReady = $true
            break
        }
    } catch {
        # 继续重试
    }
    $retryCount++
    Start-Sleep -Seconds 1
}

if ($backendReady) {
    Write-Success "✓ 后端服务就绪"
} else {
    Write-Warn "⚠ 后端服务可能仍在启动中"
    Write-Host "  查看日志: Get-Content logs\backend.log -Tail 20" -ForegroundColor Gray
}

# ==============================================
# 启动 Worker（异步任务处理）
# ==============================================
$workerProcess = $null

if (-not $SkipWorker) {
    Write-Host ""
    Write-Host "⚙️ 启动 Worker 服务..." -ForegroundColor Yellow
    
    $workerProcess = Start-Process -FilePath "python" -ArgumentList "-m", "arq", "lewis_ai_system.task_queue.WorkerSettings" `
        -RedirectStandardOutput "logs\worker.log" `
        -RedirectStandardError "logs\worker_error.log" `
        -PassThru -WindowStyle Hidden
    
    Write-Success "✓ Worker 进程已启动 (PID: $($workerProcess.Id))"
}

# ==============================================
# 启动前端
# ==============================================
$frontendProcess = $null

if (-not $SkipFrontend) {
    Write-Host ""
    Write-Host "🎨 启动前端开发服务器..." -ForegroundColor Yellow
    
    # 创建前端环境配置
    $frontendEnv = @"
NEXT_PUBLIC_API_URL=http://localhost:$BackendPort
BACKEND_URL=http://localhost:$BackendPort
NODE_ENV=development
"@
    $frontendEnv | Out-File -FilePath "frontend\.env.local" -Encoding UTF8
    
    Push-Location frontend
    $frontendProcess = Start-Process -FilePath "npm" -ArgumentList "run", "dev" `
        -RedirectStandardOutput "..\logs\frontend.log" `
        -RedirectStandardError "..\logs\frontend_error.log" `
        -PassThru -WindowStyle Hidden
    Pop-Location
    
    Write-Success "✓ 前端进程已启动 (PID: $($frontendProcess.Id))"
    
    # 等待前端启动
    Write-Host "⏳ 等待前端服务就绪..." -ForegroundColor Yellow
    $maxRetries = 30
    $retryCount = 0
    $frontendReady = $false
    
    while ($retryCount -lt $maxRetries) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:$FrontendPort" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                $frontendReady = $true
                break
            }
        } catch {
            # 继续重试
        }
        $retryCount++
        Start-Sleep -Seconds 2
    }
    
    if ($frontendReady) {
        Write-Success "✓ 前端服务就绪"
    } else {
        Write-Warn "⚠ 前端服务可能仍在启动中"
    }
}

# ==============================================
# 启动完成总结
# ==============================================
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║              ✅ Lewis AI System 启动完成！                    ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

Write-Host "🌐 服务地址:" -ForegroundColor Cyan
Write-Host "   后端 API:     http://localhost:$BackendPort" -ForegroundColor White
Write-Host "   API 文档:     http://localhost:$BackendPort/docs" -ForegroundColor White
if (-not $SkipFrontend) {
    Write-Host "   前端应用:     http://localhost:$FrontendPort" -ForegroundColor White
}

Write-Host ""
Write-Host "📋 进程信息:" -ForegroundColor Cyan
Write-Host "   后端 PID:     $($backendProcess.Id)" -ForegroundColor Gray
if ($workerProcess) {
    Write-Host "   Worker PID:   $($workerProcess.Id)" -ForegroundColor Gray
}
if ($frontendProcess) {
    Write-Host "   前端 PID:     $($frontendProcess.Id)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "📝 日志文件:" -ForegroundColor Cyan
Write-Host "   后端日志:     logs\backend.log" -ForegroundColor Gray
if (-not $SkipWorker) {
    Write-Host "   Worker日志:   logs\worker.log" -ForegroundColor Gray
}
if (-not $SkipFrontend) {
    Write-Host "   前端日志:     logs\frontend.log" -ForegroundColor Gray
}

Write-Host ""
Write-Host "🔧 管理命令:" -ForegroundColor Cyan
Write-Host "   查看日志:     Get-Content logs\backend.log -Tail -Wait" -ForegroundColor Gray
Write-Host "   停止所有:     按 Ctrl+C 或运行 .\scripts\stop-local.ps1" -ForegroundColor Gray

# 自动打开浏览器
if ($OpenBrowser -and $backendReady) {
    Write-Host ""
    Write-Info "正在打开浏览器..."
    Start-Process "http://localhost:$BackendPort/docs"
    if (-not $SkipFrontend -and $frontendReady) {
        Start-Sleep -Seconds 1
        Start-Process "http://localhost:$FrontendPort"
    }
}

Write-Host ""
Write-Host "💡 提示: 按 Ctrl+C 停止所有服务" -ForegroundColor Yellow
Write-Host ""

# ==============================================
# 等待用户中断
# ==============================================
try {
    while ($true) {
        Start-Sleep -Seconds 2
        
        # 检查进程状态
        if ($backendProcess.HasExited) {
            Write-Err "后端进程意外退出 (退出码: $($backendProcess.ExitCode))"
            Write-Host "查看日志: Get-Content logs\backend_error.log" -ForegroundColor Yellow
            break
        }
        
        if ($workerProcess -and $workerProcess.HasExited) {
            Write-Warn "Worker 进程意外退出"
        }
        
        if ($frontendProcess -and $frontendProcess.HasExited) {
            Write-Warn "前端进程意外退出"
        }
    }
} catch {
    # Ctrl+C 中断
    Write-Host ""
    Write-Info "正在停止服务..."
} finally {
    # 清理进程
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Write-Info "停止后端服务..."
        Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    
    if ($workerProcess -and -not $workerProcess.HasExited) {
        Write-Info "停止 Worker 服务..."
        Stop-Process -Id $workerProcess.Id -Force -ErrorAction SilentlyContinue
    }
    
    if ($frontendProcess -and -not $frontendProcess.HasExited) {
        Write-Info "停止前端服务..."
        Stop-Process -Id $frontendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    
    # 清理临时文件
    if (Test-Path "start_backend.py") {
        Remove-Item "start_backend.py" -Force
    }
    
    Write-Host ""
    Write-Success "所有服务已停止"
}
