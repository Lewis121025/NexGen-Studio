# Lewis AI System - 本地开发启动脚本（PowerShell版本）

param(
    [switch]$SkipFrontend = $false,
    [switch]$InstallOnly = $false
)

# 颜色函数
function Write-ColorText {
    param([string]$Text, [string]$Color = "White")
    Write-Host $Text -ForegroundColor $Color
}

# 设置错误处理
$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Lewis AI System - 本地开发模式" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 检查Python
Write-Host "🐍 检查Python环境..." -ForegroundColor Yellow

try {
    $pythonVersion = python3 --version 2>&1
    Write-ColorText "✓ $pythonVersion" "Green"
} catch {
    Write-ColorText "✗ 未找到 python3" "Red"
    Write-Host "请安装 Python 3.11 或更高版本并添加到PATH" -ForegroundColor Yellow
    exit 1
}

# 检查Node.js
Write-Host ""
Write-Host "📦 检查Node.js环境..." -ForegroundColor Yellow

try {
    $nodeVersion = node --version 2>&1
    Write-ColorText "✓ Node.js $nodeVersion" "Green"
    $hasNode = $true
} catch {
    Write-ColorText "⚠ 未找到 Node.js（前端需要）" "Yellow"
    $hasNode = $false
}

# 检查.env文件
Write-Host ""
Write-Host "⚙️  检查配置文件..." -ForegroundColor Yellow

if (-not (Test-Path ".env")) {
    Write-ColorText "⚠ 未找到 .env 文件" "Yellow"
    Write-Host "复制示例配置..." -ForegroundColor Cyan

    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-ColorText "✓ 已创建 .env 文件" "Green"
        Write-Host "请编辑 .env 文件并填入必要的API密钥" -ForegroundColor Yellow
    } else {
        Write-ColorText "✗ 未找到 .env.example 文件" "Red"
        exit 1
    }
} else {
    Write-ColorText "✓ 找到 .env 配置文件" "Green"
}

# 创建虚拟环境并安装依赖
Write-Host ""
Write-Host "📦 安装Python依赖..." -ForegroundColor Yellow

if (-not (Test-Path "venv")) {
    Write-Host "创建虚拟环境..." -ForegroundColor Cyan
    python3 -m venv venv
}

$venvPython = if ($IsLinux -or $IsMacOS) { "venv/bin/python" } else { "venv\Scripts\python.exe" }

& $venvPython -m pip install --quiet -e ".[dev]" 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-ColorText "✓ Python依赖已安装" "Green"
} else {
    # 尝试不安装可选依赖
    & $venvPython -m pip install --quiet -e . 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-ColorText "✓ Python依赖已安装（基础版）" "Green"
    } else {
        Write-ColorText "✗ 依赖安装失败" "Red"
        exit 1
    }
}

# 安装前端依赖
if ($hasNode -and -not $SkipFrontend -and (Test-Path "frontend")) {
    Write-Host ""
    Write-Host "📦 安装前端依赖..." -ForegroundColor Yellow

    Push-Location frontend

    if (-not (Test-Path "node_modules")) {
        Write-Host "安装npm包..." -ForegroundColor Cyan
        npm install --silent 2>&1 | Out-Null
    }

    if ($LASTEXITCODE -eq 0) {
        Write-ColorText "✓ 前端依赖已安装" "Green"
    } else {
        Write-ColorText "⚠ 前端依赖安装失败" "Yellow"
        Write-Host "可以稍后手动运行：cd frontend && npm install" -ForegroundColor Yellow
    }

    Pop-Location
}

# 仅安装模式
if ($InstallOnly) {
    Write-Host ""
    Write-ColorText "✓ 依赖安装完成！" "Green"
    exit 0
}

# 启动后端服务
Write-Host ""
Write-ColorText "🚀 启动服务..." "Green"
Write-Host ""

Write-Host "启动后端服务..." -ForegroundColor Cyan
Write-Host "后端地址: http://localhost:8000" -ForegroundColor Gray
Write-Host "API文档:  http://localhost:8000/docs" -ForegroundColor Gray
Write-Host ""

# 检查端口是否被占用
$portInUse = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Where-Object { $_.State -eq "Listen" }
if ($portInUse) {
    Write-ColorText "⚠ 端口8000已被占用" "Yellow"
    Write-Host "请关闭占用端口的进程或修改端口配置" -ForegroundColor Yellow
    Write-Host ""
}

# 启动后端
$backendJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    & $using:venvPython -m uvicorn lewis_ai_system.main:app --host 0.0.0.0 --port 8000 --reload
}

# 等待后端启动
Start-Sleep -Seconds 3

# 验证后端是否启动成功
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/healthz" -TimeoutSec 5 -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-ColorText "✓ 后端服务启动成功！" "Green"
    } else {
        throw "后端返回非200状态码"
    }
} catch {
    Write-ColorText "✗ 后端服务启动失败" "Red"
    Write-Host $_.Exception.Message -ForegroundColor Red
    Stop-Job $backendJob -Force
    exit 1
}

# 启动前端（如果需要）
$frontendJob = $null
if ($hasNode -and -not $SkipFrontend -and (Test-Path "frontend") -and (Test-Path "frontend/node_modules")) {
    Write-Host ""
    Write-Host "启动前端服务..." -ForegroundColor Cyan
    Write-Host "前端地址: http://localhost:3000" -ForegroundColor Gray
    Write-Host ""

    Push-Location frontend
    $frontendJob = Start-Job -ScriptBlock {
        Set-Location $using:PWD
        npm run dev
    }
    Pop-Location

    # 等待前端启动
    Start-Sleep -Seconds 5

    # 验证前端是否启动成功
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:3000" -TimeoutSec 5 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-ColorText "✓ 前端服务启动成功！" "Green"
        } else {
            throw "前端返回非200状态码"
        }
    } catch {
        Write-ColorText "⚠ 前端服务可能启动失败" "Yellow"
        Write-Host "请检查前端错误信息" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-ColorText "🎉 Lewis AI System 已启动！" "Green"
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "访问地址：" -ForegroundColor White
Write-Host "  后端API:  http://localhost:8000" -ForegroundColor Gray
Write-Host "  API文档:  http://localhost:8000/docs" -ForegroundColor Gray
if ($frontendJob) {
    Write-Host "  前端界面: http://localhost:3000" -ForegroundColor Gray
}
Write-Host ""
Write-Host "按 Ctrl+C 停止服务" -ForegroundColor Yellow
Write-Host ""

# 等待用户中断
try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
} finally {
    Write-Host ""
    Write-Host "正在停止服务..." -ForegroundColor Yellow

    if ($backendJob) {
        Stop-Job $backendJob -Force
        Remove-Job $backendJob -Force
    }

    if ($frontendJob) {
        Stop-Job $frontendJob -Force
        Remove-Job $frontendJob -Force
    }

    Write-ColorText "✓ 服务已停止" "Green"
}
