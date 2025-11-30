# Lewis AI System - 本地完整功能演示脚本
# 此脚本将启动所有必要的服务以演示完整功能

Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Lewis AI System - 本地完整功能演示" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# 检查 .env 文件
if (-not (Test-Path ".env")) {
    Write-Host "✗ .env 文件不存在！" -ForegroundColor Red
    Write-Host "请先创建 .env 文件并配置必要的 API 密钥" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ 发现 .env 配置文件" -ForegroundColor Green

# 读取环境变量
$envContent = Get-Content .env -Raw

# 检查关键配置
$missingConfig = @()

if ($envContent -notmatch '(?m)^OPENROUTER_API_KEY\s*=\s*\S+') {
    $missingConfig += "OPENROUTER_API_KEY"
}

if ($envContent -notmatch '(?m)^E2B_API_KEY\s*=\s*\S+') {
    $missingConfig += "E2B_API_KEY"
}

if ($missingConfig.Count -gt 0) {
    Write-Host "⚠ 警告: 以下配置项缺失或未设置:" -ForegroundColor Yellow
    foreach ($item in $missingConfig) {
        Write-Host "  • $item" -ForegroundColor Yellow
    }
    Write-Host "某些功能可能无法正常工作" -ForegroundColor Yellow
    Write-Host ""
}

# 检查数据库配置
$useDocker = $false
if ($envContent -match '(?m)^DATABASE_URL\s*=\s*postgresql') {
    $useDocker = $true
    Write-Host "✓ 检测到 PostgreSQL 配置，将使用 Docker 服务" -ForegroundColor Green
} elseif ($envContent -match '(?m)^DATABASE_URL\s*=\s*sqlite') {
    Write-Host "✓ 检测到 SQLite 配置，将使用本地数据库" -ForegroundColor Green
} else {
    Write-Host "⚠ 警告: DATABASE_URL 未正确配置" -ForegroundColor Yellow
}

Write-Host ""

# 检查 Docker（如果需要）
if ($useDocker) {
    try {
        docker --version | Out-Null
        Write-Host "✓ Docker 已就绪" -ForegroundColor Green
    } catch {
        Write-Host "✗ Docker 未安装或未启动" -ForegroundColor Red
        Write-Host "请先启动 Docker Desktop" -ForegroundColor Yellow
        exit 1
    }
}

# 检查 Python 环境
Write-Host "🔍 检查 Python 环境..." -ForegroundColor Yellow
try {
    $pythonVersion = python3 --version 2>&1
    Write-Host "✓ $pythonVersion" -ForegroundColor Green
    
    # 检查是否安装了依赖
    $installed = python3 -c "import lewis_ai_system" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "⚠ 检测到依赖未安装，正在安装..." -ForegroundColor Yellow
        pip install -e .
        if ($LASTEXITCODE -ne 0) {
            Write-Host "✗ 依赖安装失败" -ForegroundColor Red
            exit 1
        }
        Write-Host "✓ 依赖安装完成" -ForegroundColor Green
    } else {
        Write-Host "✓ Python 依赖已安装" -ForegroundColor Green
    }
} catch {
    Write-Host "✗ Python 未安装或不在 PATH 中" -ForegroundColor Red
    exit 1
}

Write-Host ""

# 检查 Node.js 环境（前端）
Write-Host "🔍 检查 Node.js 环境..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version 2>&1
    Write-Host "✓ Node.js $nodeVersion" -ForegroundColor Green
    
    # 检查前端依赖
    if (-not (Test-Path "frontend/node_modules")) {
        Write-Host "⚠ 检测到前端依赖未安装，正在安装..." -ForegroundColor Yellow
        Push-Location frontend
        npm install
        if ($LASTEXITCODE -ne 0) {
            Write-Host "✗ 前端依赖安装失败" -ForegroundColor Red
            Pop-Location
            exit 1
        }
        Pop-Location
        Write-Host "✓ 前端依赖安装完成" -ForegroundColor Green
    } else {
        Write-Host "✓ 前端依赖已安装" -ForegroundColor Green
    }
} catch {
    Write-Host "⚠ Node.js 未安装，前端功能将不可用" -ForegroundColor Yellow
}

Write-Host ""

# 启动数据库服务（如果需要）
if ($useDocker) {
    Write-Host "🗄️ 启动数据库服务..." -ForegroundColor Yellow
    
    # 检查数据库服务是否已运行
    $postgresRunning = docker compose ps postgres --format json 2>$null | ConvertFrom-Json | Where-Object { $_.State -eq "running" }
    
    if (-not $postgresRunning) {
        Write-Host "  启动 PostgreSQL、Redis、Weaviate..." -ForegroundColor Gray
        docker compose up -d postgres redis weaviate
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "✗ 数据库服务启动失败" -ForegroundColor Red
            exit 1
        }
        
        # 等待数据库就绪
        Write-Host "⏳ 等待数据库就绪..." -ForegroundColor Yellow
        $maxRetries = 30
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
        
        Write-Host "✓ 数据库服务已就绪" -ForegroundColor Green
    } else {
        Write-Host "✓ 数据库服务已在运行" -ForegroundColor Green
    }
    
    Write-Host ""
}

# 初始化数据库
Write-Host "🧱 初始化数据库..." -ForegroundColor Yellow

if ($useDocker) {
    # 使用 Docker 执行初始化
    docker compose run --rm -e SKIP_ENTRYPOINT_DB_INIT=1 lewis-api python3 -m lewis_ai_system.cli init-db 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "⚠ 数据库初始化可能失败，但继续执行..." -ForegroundColor Yellow
    } else {
        Write-Host "✓ 数据库初始化完成" -ForegroundColor Green
    }
} else {
    # 本地执行初始化
    python3 -m lewis_ai_system.cli init-db
    if ($LASTEXITCODE -ne 0) {
        Write-Host "⚠ 数据库初始化可能失败，但继续执行..." -ForegroundColor Yellow
    } else {
        Write-Host "✓ 数据库初始化完成" -ForegroundColor Green
    }
}

Write-Host ""

# 启动后端服务
Write-Host "🚀 启动后端服务..." -ForegroundColor Yellow

if ($useDocker) {
    # 检查后端是否已运行
    $apiRunning = docker compose ps lewis-api --format json 2>$null | ConvertFrom-Json | Where-Object { $_.State -eq "running" }
    
    if (-not $apiRunning) {
        Write-Host "  使用 Docker 启动后端..." -ForegroundColor Gray
        docker compose up -d lewis-api
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "✗ 后端启动失败" -ForegroundColor Red
            exit 1
        }
        
        # 等待后端就绪
        Write-Host "⏳ 等待后端服务就绪..." -ForegroundColor Yellow
        $maxRetries = 30
        $retryCount = 0
        $apiReady = $false
        
        while ($retryCount -lt $maxRetries) {
            try {
                $response = Invoke-WebRequest -Uri "http://localhost:8000/healthz" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
                if ($response.StatusCode -eq 200) {
                    $apiReady = $true
                    break
                }
            } catch {
                # 继续重试
            }
            $retryCount++
            Start-Sleep -Seconds 1
        }
        
        if (-not $apiReady) {
            Write-Host "⚠ 后端服务可能未完全就绪，但继续执行..." -ForegroundColor Yellow
        } else {
            Write-Host "✓ 后端服务已就绪" -ForegroundColor Green
        }
    } else {
        Write-Host "✓ 后端服务已在运行" -ForegroundColor Green
    }
} else {
    # 本地启动后端
    Write-Host "  在后台启动后端服务..." -ForegroundColor Gray
    $backendJob = Start-Job -ScriptBlock {
        Set-Location $using:PWD
        uvicorn lewis_ai_system.main:app --reload --host 0.0.0.0 --port 8000
    }
    
    # 等待后端就绪
    Write-Host "⏳ 等待后端服务就绪..." -ForegroundColor Yellow
    $maxRetries = 30
    $retryCount = 0
    $apiReady = $false
    
    while ($retryCount -lt $maxRetries) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8000/healthz" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                $apiReady = $true
                break
            }
        } catch {
            # 继续重试
        }
        $retryCount++
        Start-Sleep -Seconds 1
    }
    
    if (-not $apiReady) {
        Write-Host "⚠ 后端服务可能未完全就绪，但继续执行..." -ForegroundColor Yellow
    } else {
        Write-Host "✓ 后端服务已就绪" -ForegroundColor Green
    }
}

Write-Host ""

# 启动前端服务
Write-Host "🎨 启动前端服务..." -ForegroundColor Yellow

try {
    $nodeVersion = node --version 2>&1
    if ($nodeVersion) {
        # 检查前端是否已运行
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                Write-Host "✓ 前端服务已在运行" -ForegroundColor Green
            }
        } catch {
            # 前端未运行，启动它
            Write-Host "  在后台启动前端服务..." -ForegroundColor Gray
            Push-Location frontend
            $frontendJob = Start-Job -ScriptBlock {
                Set-Location $using:PWD
                npm run dev
            }
            Pop-Location
            
            # 等待前端就绪
            Write-Host "⏳ 等待前端服务就绪..." -ForegroundColor Yellow
            Start-Sleep -Seconds 5
            
            Write-Host "✓ 前端服务已启动" -ForegroundColor Green
        }
    }
} catch {
    Write-Host "⚠ 前端服务启动失败或 Node.js 未安装" -ForegroundColor Yellow
}

Write-Host ""

# 显示服务信息
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  ✅ 本地演示环境已就绪！" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 服务地址:" -ForegroundColor Cyan
Write-Host "  • 前端界面: http://localhost:3000" -ForegroundColor White
Write-Host "  • 后端 API: http://localhost:8000" -ForegroundColor White
Write-Host "  • API 文档: http://localhost:8000/docs" -ForegroundColor White
Write-Host "  • 健康检查: http://localhost:8000/healthz" -ForegroundColor White
Write-Host ""
Write-Host "📝 功能演示:" -ForegroundColor Cyan
Write-Host "  1. 访问前端界面体验完整功能" -ForegroundColor Gray
Write-Host "  2. 使用 API 文档测试后端接口" -ForegroundColor Gray
Write-Host "  3. 创建创意项目或通用会话" -ForegroundColor Gray
Write-Host ""
Write-Host "🛑 停止服务:" -ForegroundColor Cyan
if ($useDocker) {
    Write-Host "  docker compose down        # 停止所有 Docker 服务" -ForegroundColor Gray
} else {
    Write-Host "  Stop-Job -Name *           # 停止后台任务" -ForegroundColor Gray
    Write-Host "  Get-Job | Remove-Job       # 清理后台任务" -ForegroundColor Gray
}
Write-Host ""
Write-Host "📊 查看日志:" -ForegroundColor Cyan
if ($useDocker) {
    Write-Host "  docker compose logs -f     # 查看所有服务日志" -ForegroundColor Gray
    Write-Host "  docker compose logs -f lewis-api  # 仅查看后端日志" -ForegroundColor Gray
} else {
    Write-Host "  查看终端输出或日志文件" -ForegroundColor Gray
}
Write-Host ""

# 询问是否打开浏览器
$openBrowser = Read-Host "是否在浏览器中打开前端界面? (Y/n)"
if ($openBrowser -ne 'n' -and $openBrowser -ne 'N') {
    Start-Process "http://localhost:3000"
    Start-Sleep -Seconds 2
    Start-Process "http://localhost:8000/docs"
}

Write-Host ""
Write-Host "✨ 演示环境已准备就绪，祝您使用愉快！" -ForegroundColor Green
Write-Host ""








