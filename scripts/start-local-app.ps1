# Lewis AI System - 本地应用启动脚本
# 分别启动后端API和前端开发服务器

param(
    [switch]$SkipFrontend = $false,
    [switch]$RebuildFrontend = $false,
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000,
    [switch]$OpenBrowser = $true
)

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[ERR ] $msg" -ForegroundColor Red }
function Write-Success($msg) { Write-Host "[SUCCESS] $msg" -ForegroundColor Green }

Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Lewis AI System - 本地应用启动" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# 检查.env文件
if (-not (Test-Path ".env")) {
    Write-Err ".env 文件不存在！"
    Write-Host "请先运行 '.\scripts\start-local-databases.ps1' 创建配置" -ForegroundColor Yellow
    exit 1
}

Write-Success "✓ 找到 .env 配置文件"

# 检查必要配置
Write-Host ""
Write-Host "🔍 检查配置..." -ForegroundColor Yellow

$envContent = Get-Content ".env" -Raw
$dbUrl = ($envContent -match "DATABASE_URL=(.+)" | ForEach-Object { $matches[1] }) | Select-Object -First 1
$redisUrl = ($envContent -match "REDIS_URL=(.+)" | ForEach-Object { $matches[1] }) | Select-Object -First 1

if (-not $dbUrl) {
    Write-Err "DATABASE_URL 未配置"
    exit 1
}

if (-not $redisUrl) {
    Write-Err "REDIS_URL 未配置"
    exit 1
}

Write-Success "✓ 数据库配置正确"

# 检查Python环境
Write-Host ""
Write-Host "🐍 检查Python环境..." -ForegroundColor Yellow

try {
    $pythonVersion = python3 --version 2>&1
    Write-Success "✓ $pythonVersion"
} catch {
    Write-Err "Python未安装或未添加到PATH"
    exit 1
}

# 安装/检查Python依赖
Write-Host ""
Write-Host "📦 检查Python依赖..." -ForegroundColor Yellow

$hasPackage = python3 -c "import fastapi, uvicorn, sqlalchemy" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Info "安装Python依赖..."
    python3 -m pip install -e .
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Python依赖安装失败"
        exit 1
    }
}
Write-Success "✓ Python依赖已就绪"

# 检查Node.js环境
Write-Host ""
Write-Host "📦 检查Node.js环境..." -ForegroundColor Yellow

if (-not $SkipFrontend) {
    try {
        $nodeVersion = node --version 2>&1
        $npmVersion = npm --version 2>&1
        Write-Success "✓ Node.js $nodeVersion, npm $npmVersion"
    } catch {
        Write-Warn "Node.js未安装或未添加到PATH（将跳过前端启动）"
        $SkipFrontend = $true
    }
}

# 检查前端依赖
if (-not $SkipFrontend) {
    Write-Host ""
    Write-Host "📦 检查前端依赖..." -ForegroundColor Yellow
    
    if (-not (Test-Path "frontend\package.json")) {
        Write-Warn "未找到frontend/package.json，跳过前端启动"
        $SkipFrontend = $true
    } else {
        if (-not (Test-Path "frontend\node_modules")) {
            Write-Info "安装前端依赖..."
            Set-Location frontend
            npm install
            if ($LASTEXITCODE -ne 0) {
                Write-Err "前端依赖安装失败"
                Set-Location ..
                $SkipFrontend = $true
            } else {
                Write-Success "✓ 前端依赖安装完成"
                Set-Location ..
            }
        } else {
            Write-Success "✓ 前端依赖已存在"
        }

        # 可选：重新构建前端
        if ($RebuildFrontend -and -not $SkipFrontend) {
            Write-Info "重新构建前端..."
            Set-Location frontend
            npm run build
            if ($LASTEXITCODE -eq 0) {
                Write-Success "✓ 前端构建完成"
            } else {
                Write-Warn "⚠ 前端构建失败，但可以继续"
            }
            Set-Location ..
        }
    }
}

# 创建日志目录
if (-not (Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" -Force | Out-Null
}

# ==============================================
# 启动后端API
# ==============================================
Write-Host ""
Write-Host "🚀 启动后端API服务..." -ForegroundColor Yellow

$backendProcess = $null
$backendLogFile = "logs\backend.log"

try {
    # 创建启动脚本
    $startScript = @"
import uvicorn
from lewis_ai_system.main import app

if __name__ == "__main__":
    uvicorn.run(
        "lewis_ai_system.main:app",
        host="0.0.0.0",
        port=$BackendPort,
        reload=True,
        log_level="info",
        access_log=True
    )
"@
    
    $startScript | Out-File -FilePath "start_backend.py" -Encoding UTF8

    # 启动后端
    Write-Info "在端口 $BackendPort 启动后端服务..."
    $backendProcess = Start-Process -FilePath "python" -ArgumentList "start_backend.py" -RedirectStandardOutput $backendLogFile -RedirectStandardError $backendLogFile -PassThru -WindowStyle Normal
    
    Write-Success "✓ 后端进程已启动 (PID: $($backendProcess.Id))"
} catch {
    Write-Err "启动后端失败: $($_.Exception.Message)"
    exit 1
}

# 等待后端启动
Write-Host ""
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
}

# ==============================================
# 启动前端（可选）
# ==============================================
$frontendProcess = $null

if (-not $SkipFrontend) {
    Write-Host ""
    Write-Host "🎨 启动前端开发服务器..." -ForegroundColor Yellow

    $frontendLogFile = "logs\frontend.log"

    try {
        # 创建前端环境配置文件
        $frontendEnv = @"
NEXT_PUBLIC_API_URL=http://localhost:$BackendPort
BACKEND_URL=http://localhost:$BackendPort
NODE_ENV=development
"@
        
        $frontendEnv | Out-File -FilePath "frontend\.env.local" -Encoding UTF8

        # 启动前端
        Set-Location frontend
        $frontendProcess = Start-Process -FilePath "npm" -ArgumentList "run", "dev" -RedirectStandardOutput "..\$frontendLogFile" -RedirectStandardError "..\$frontendLogFile" -PassThru -WindowStyle Normal
        Set-Location ..
        
        Write-Success "✓ 前端进程已启动 (PID: $($frontendProcess.Id))"
    } catch {
        Write-Err "启动前端失败: $($_.Exception.Message)"
        Set-Location ..
    }

    # 等待前端启动
    Write-Host ""
    Write-Host "⏳ 等待前端服务就绪..." -ForegroundColor Yellow

    $maxRetries = 20
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
# 完成总结
# ==============================================
Write-Host ""
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  ✅ Lewis AI System 启动完成！" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""

Write-Host "🌐 服务地址:" -ForegroundColor Cyan
Write-Host "  后端API:     http://localhost:$BackendPort" -ForegroundColor Gray
Write-Host "  API文档:     http://localhost:$BackendPort/docs" -ForegroundColor Gray
if (-not $SkipFrontend) {
    Write-Host "  前端应用:    http://localhost:$FrontendPort" -ForegroundColor Gray
}

Write-Host ""
Write-Host "📋 进程信息:" -ForegroundColor Cyan
if ($backendProcess) {
    Write-Host "  后端PID:     $($backendProcess.Id)" -ForegroundColor Gray
}
if ($frontendProcess) {
    Write-Host "  前端PID:     $($frontendProcess.Id)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "📝 日志文件:" -ForegroundColor Cyan
Write-Host "  后端日志:    logs\backend.log" -ForegroundColor Gray
if (-not $SkipFrontend) {
    Write-Host "  前端日志:    logs\frontend.log" -ForegroundColor Gray
}

Write-Host ""
Write-Host "🔧 管理命令:" -ForegroundColor Cyan
Write-Host "  停止服务:    按 Ctrl+C" -ForegroundColor Gray
Write-Host "  查看日志:    Get-Content logs\*.log -Tail -Follow" -ForegroundColor Gray
Write-Host "  重启后端:    Stop-Process -Id $($backendProcess.Id); 再次运行此脚本" -ForegroundColor Gray

# 自动打开浏览器
if ($OpenBrowser -and $backendReady) {
    Write-Host ""
    Write-Info "正在打开浏览器..."
    try {
        Start-Process "http://localhost:$BackendPort/docs"
        if (-not $SkipFrontend -and $frontendReady) {
            Start-Process "http://localhost:$FrontendPort"
        }
    } catch {
        Write-Warn "无法自动打开浏览器，请手动访问上述地址"
    }
}

Write-Host ""
Write-Host "💡 提示:" -ForegroundColor Yellow
Write-Host "  • 首次启动可能需要更多时间下载依赖" -ForegroundColor Gray
Write-Host "  • 如果遇到问题，请检查日志文件" -ForegroundColor Gray
Write-Host "  • 开发过程中，文件修改会自动重新加载" -ForegroundColor Gray

Write-Host ""
Write-Host "按 Ctrl+C 停止所有服务..." -ForegroundColor Yellow

# 等待用户中断
try {
    while ($true) {
        Start-Sleep -Seconds 1
        
        # 检查后端进程是否还在运行
        if ($backendProcess -and $backendProcess.HasExited) {
            Write-Err "后端进程意外退出"
            break
        }
        
        # 检查前端进程是否还在运行
        if ($frontendProcess -and $frontendProcess.HasExited -and -not $SkipFrontend) {
            Write-Warn "前端进程意外退出"
            break
        }
    }
} catch {
    Write-Host ""
    Write-Info "正在停止服务..."
} finally {
    # 清理进程
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Write-Info "停止后端服务..."
        Stop-Process -Id $backendProcess.Id -Force
    }
    
    if ($frontendProcess -and -not $frontendProcess.HasExited) {
        Write-Info "停止前端服务..."
        Stop-Process -Id $frontendProcess.Id -Force
    }
    
    # 清理临时文件
    if (Test-Path "start_backend.py") {
        Remove-Item "start_backend.py" -Force
    }
    
    Write-Host ""
    Write-Success "所有服务已停止"
}

