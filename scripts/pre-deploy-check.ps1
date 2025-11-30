# Lewis AI System - 部署前检查脚本
# 验证环境配置、依赖和关键文件

Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Lewis AI System - 部署前检查" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

$errors = 0
$warnings = 0

# 检查.env文件
Write-Host "🔍 检查环境配置..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Write-Host "  ✗ .env 文件不存在" -ForegroundColor Red
    Write-Host "    建议: 复制 .env.example 并填写配置" -ForegroundColor Yellow
    $errors++
} else {
    Write-Host "  ✓ .env 文件存在" -ForegroundColor Green
    
    # 检查关键配置
    $envContent = Get-Content ".env" -Raw
    
    $requiredKeys = @(
        "OPENROUTER_API_KEY",
        "DATABASE_URL",
        "JWT_SECRET_KEY"
    )
    
    foreach ($key in $requiredKeys) {
        if ($envContent -match "$key=.+") {
            if ($envContent -match "$key=(.+)") {
                $value = $matches[1].Trim()
                if ($value -match "your-.*-here" -or $value -match "change") {
                    Write-Host "  ⚠  $key 需要修改" -ForegroundColor Yellow
                    $warnings++
                } else {
                    Write-Host "  ✓ $key 已配置" -ForegroundColor Green
                }
            }
        } else {
            Write-Host "  ✗ $key 未配置" -ForegroundColor Red
            $errors++
        }
    }
}

Write-Host ""

# 检查Docker
Write-Host "🔍 检查Docker环境..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version
    Write-Host "  ✓ Docker 已安装: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Docker 未安装" -ForegroundColor Red
    $errors++
}

try {
    $composeVersion = docker compose version
    Write-Host "  ✓ Docker Compose 已安装: $composeVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Docker Compose 未安装" -ForegroundColor Red
    $errors++
}

Write-Host ""

# 检查关键文件
Write-Host "🔍 检查关键文件..." -ForegroundColor Yellow

$criticalFiles = @(
    "docker-compose.yml",
    "Dockerfile",
    "pyproject.toml",
    "src/lewis_ai_system/main.py",
    "frontend/package.json",
    "scripts/db-init.ps1",
    "scripts/seed_data.py",
    "BETA_USER_GUIDE.md"
)

foreach ($file in $criticalFiles) {
    if (Test-Path $file) {
        Write-Host "  ✓ $file" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $file 缺失" -ForegroundColor Red
        $errors++
    }
}

Write-Host ""

# 检查Python依赖
Write-Host "🔍 检查Python依赖..." -ForegroundColor Yellow
if (Test-Path "pyproject.toml") {
    $content = Get-Content "pyproject.toml" -Raw
    $requiredPackages = @("fastapi", "sqlalchemy", "pydantic", "jose")
    
    foreach ($pkg in $requiredPackages) {
        if ($content -match $pkg) {
            Write-Host "  ✓ $pkg 已在依赖中" -ForegroundColor Green
        } else {
            Write-Host "  ⚠  $pkg 可能缺失" -ForegroundColor Yellow
            $warnings++
        }
    }
}

Write-Host ""

# 检查前端依赖
Write-Host "🔍 检查前端依赖..." -ForegroundColor Yellow
if (Test-Path "frontend/package.json") {
    $content = Get-Content "frontend/package.json" -Raw
    $requiredPackages = @("next", "react", "zustand")
    
    foreach ($pkg in $requiredPackages) {
        if ($content -match $pkg) {
            Write-Host "  ✓ $pkg 已在依赖中" -ForegroundColor Green
        } else {
            Write-Host "  ⚠  $pkg 可能缺失" -ForegroundColor Yellow
            $warnings++
        }
    }
}

Write-Host ""

# 检查数据库迁移文件
Write-Host "🔍 检查数据库迁移..." -ForegroundColor Yellow
if (Test-Path "alembic/versions") {
    $migrations = Get-ChildItem "alembic/versions/*.py" | Where-Object { $_.Name -ne "__init__.py" }
    Write-Host "  ✓ 找到 $($migrations.Count) 个迁移文件" -ForegroundColor Green
} else {
    Write-Host "  ⚠  迁移目录不存在" -ForegroundColor Yellow
    $warnings++
}

Write-Host ""

# 检查认证模块
Write-Host "🔍 检查认证模块..." -ForegroundColor Yellow
$authFiles = @(
    "src/lewis_ai_system/routers/auth.py",
    "frontend/src/lib/stores/authStore.ts",
    "frontend/src/app/login/page.tsx",
    "frontend/src/components/layout/AuthGuard.tsx"
)

foreach ($file in $authFiles) {
    if (Test-Path $file) {
        Write-Host "  ✓ $file" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $file 缺失" -ForegroundColor Red
        $errors++
    }
}

Write-Host ""

# 检查治理模块
Write-Host "🔍 检查治理模块..." -ForegroundColor Yellow
$govFiles = @(
    "src/lewis_ai_system/routers/governance.py",
    "frontend/src/app/governance/page.tsx"
)

foreach ($file in $govFiles) {
    if (Test-Path $file) {
        Write-Host "  ✓ $file" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $file 缺失" -ForegroundColor Red
        $errors++
    }
}

Write-Host ""

# 总结
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
if ($errors -eq 0 -and $warnings -eq 0) {
    Write-Host "  ✅ 检查通过！系统已准备就绪" -ForegroundColor Green
    Write-Host "═══════════════════════════════════════════════" -ForegroundColor Green
    Write-Host ""
    Write-Host "📝 下一步操作:" -ForegroundColor Cyan
    Write-Host "  1. 确认 .env 配置正确" -ForegroundColor White
    Write-Host "  2. 运行: .\start.ps1" -ForegroundColor White
    Write-Host "  3. 访问: http://localhost:3000" -ForegroundColor White
    Write-Host ""
    exit 0
} elseif ($errors -eq 0) {
    Write-Host "  ⚠️  检查完成 (有 $warnings 个警告)" -ForegroundColor Yellow
    Write-Host "═══════════════════════════════════════════════" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "系统可以启动，但建议解决上述警告" -ForegroundColor Yellow
    Write-Host ""
    exit 0
} else {
    Write-Host "  ❌ 检查失败 ($errors 个错误, $warnings 个警告)" -ForegroundColor Red
    Write-Host "═══════════════════════════════════════════════" -ForegroundColor Red
    Write-Host ""
    Write-Host "请修复上述错误后再启动系统" -ForegroundColor Red
    Write-Host ""
    exit 1
}
