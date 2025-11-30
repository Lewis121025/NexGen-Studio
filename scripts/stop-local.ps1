# Lewis AI System - 停止本地服务脚本

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Success($msg) { Write-Host "[OK  ] $msg" -ForegroundColor Green }

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "║     Lewis AI System - 停止本地服务                            ║" -ForegroundColor Yellow
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
Write-Host ""

# 停止 uvicorn/FastAPI 进程
Write-Info "查找并停止后端进程..."
$uvicornProcesses = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*uvicorn*" -or $_.CommandLine -like "*lewis_ai_system*"
}

if ($uvicornProcesses) {
    $uvicornProcesses | ForEach-Object {
        Write-Info "停止进程 PID: $($_.Id)"
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Success "✓ 后端进程已停止"
} else {
    Write-Info "未发现运行中的后端进程"
}

# 停止 Node.js/前端进程
Write-Info "查找并停止前端进程..."
$nodeProcesses = Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*next*" -or $_.CommandLine -like "*frontend*"
}

if ($nodeProcesses) {
    $nodeProcesses | ForEach-Object {
        Write-Info "停止进程 PID: $($_.Id)"
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Success "✓ 前端进程已停止"
} else {
    Write-Info "未发现运行中的前端进程"
}

# 停止 ARQ Worker 进程
Write-Info "查找并停止 Worker 进程..."
$workerProcesses = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*arq*" -or $_.CommandLine -like "*task_queue*"
}

if ($workerProcesses) {
    $workerProcesses | ForEach-Object {
        Write-Info "停止进程 PID: $($_.Id)"
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Success "✓ Worker 进程已停止"
} else {
    Write-Info "未发现运行中的 Worker 进程"
}

# 清理临时文件
if (Test-Path "start_backend.py") {
    Remove-Item "start_backend.py" -Force
}

Write-Host ""
Write-Success "所有 Lewis AI System 服务已停止"
Write-Host ""
