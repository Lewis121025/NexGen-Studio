# 快速入门指南 🚀

本指南帮助你在5分钟内启动Lewis AI System并体验核心功能。

## 前置要求

- Python 3.11+ （推荐3.13）
- Node.js 18+ （前端开发需要）
- PostgreSQL 15+（本地安装）
- Redis（可选，可用内存缓存替代）
- 至少一个AI Provider API Key（OpenRouter/Runway/Pika等）

## 步骤1：获取代码

```bash
git clone https://github.com/yourusername/Lewis_AI_System.git
cd Lewis_AI_System
```

## 步骤2：安装本地数据库服务

### PostgreSQL 安装

**Windows (推荐使用 Chocolatey):**
```powershell
# 安装 Chocolatey (如果没有)
# https://chocolatey.org/install

# 安装 PostgreSQL
choco install postgresql15 -y

# 启动服务
net start postgresql-x64-15
```

**或手动安装:**
- 下载: https://www.postgresql.org/download/windows/
- 安装后记住设置的密码

**创建数据库用户和数据库:**
```sql
-- 使用 psql 或 pgAdmin 执行
CREATE USER lewis WITH PASSWORD 'lewis_pass';
CREATE DATABASE lewis_db OWNER lewis;
GRANT ALL PRIVILEGES ON DATABASE lewis_db TO lewis;
```

### Redis 安装（可选）

**Windows:**
```powershell
choco install redis-64 -y
net start Redis
```

如果不想安装 Redis，可以在 `.env` 中设置 `REDIS_ENABLED=false`，系统会自动使用内存缓存。

## 步骤3：配置环境变量

```bash
# 复制环境变量模板（如果有的话）
# 或直接编辑 .env 文件
```

**本地运行配置示例 (.env):**
```env
APP_ENV=development
LOG_LEVEL=INFO
SECRET_KEY=your-secret-key-here

# 数据库配置（本地 PostgreSQL）
DATABASE_URL=postgresql+asyncpg://lewis:lewis_pass@localhost:5432/lewis_db

# Redis缓存（本地 Redis，可选）
REDIS_ENABLED=true
REDIS_URL=redis://localhost:6379/0

# LLM Provider配置
LLM_PROVIDER_MODE=openrouter
OPENROUTER_API_KEY=sk-or-xxx

# 视频生成配置
VIDEO_PROVIDER=doubao
DOUBAO_API_KEY=your-doubao-key

# 代理配置（本地代理）
HTTP_PROXY=http://127.0.0.1:7897
HTTPS_PROXY=http://127.0.0.1:7897
```

## 步骤4：启动系统

### 一键启动（推荐）

**Windows PowerShell:**
```powershell
# 检查本地服务状态
.\scripts\setup-local-services.ps1 -CheckOnly

# 初始化数据库并启动
.\scripts\start-local.ps1 -InitDatabase
```

**后续启动（数据库已初始化）:**
```powershell
.\scripts\start-local.ps1
```

### 手动启动

```bash
# 1. 安装Python依赖
pip install -e .

# 2. 初始化数据库
python -m lewis_ai_system.cli init-db

# 3. 启动后端
uvicorn lewis_ai_system.main:app --host 0.0.0.0 --port 8000 --reload

# 4. 在新终端启动前端
cd frontend
npm install
npm run dev

# 5. (可选) 启动异步任务 Worker
python -m arq lewis_ai_system.task_queue.WorkerSettings
```


## 步骤4：访问系统

- **前端界面**: http://localhost:3000
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs

## 步骤5：验证安装

运行验证脚本：
```bash
python verify_deployment.py
```

应该看到所有检查项都显示 ✅。

## 快速体验功能

### 体验1：创作模式（视频生成）

1. 打开 http://localhost:3000
2. 点击"创作模式"卡片
3. 在输入框输入：
   ```
   制作一个30秒的科技产品宣传视频，展示AI助手的核心功能
   ```
4. 按 Ctrl+Enter（或点击"生成"）
5. 等待工作流完成：
   - 文案扩展 → 脚本生成 → 分镜规划 → 视频生成 → 质量检查
6. 完成后点击项目查看视频预览和分镜

### 体验2：通用模式（任务执行）

1. 返回首页，点击"通用模式"
2. 输入任务：
   ```
   搜索"2024年AI发展趋势"并总结前3条结果
   ```
3. 观察ReAct循环的思考和执行过程
4. 查看最终整理的结果

### 体验3：设置页面

1. 点击左侧边栏的"设置"图标
2. 在"API Keys"标签下管理你的API密钥
3. 在"Appearance"标签切换主题（Light/Dark/System）
4. 在"Profile"标签查看系统信息

## 运行测试

验证系统完整性：
```bash
# 运行所有58个测试
pytest

# 快速验证核心功能
pytest tests/test_full_system.py tests/test_creative_workflow.py tests/test_general_session.py -v
```

## 常见问题

### Q1: 端口被占用
```bash
# 检查端口占用
# Windows
netstat -ano | findstr :3000
netstat -ano | findstr :8000

# Linux/macOS
lsof -i :3000
lsof -i :8000
```

解决：修改 `.env` 中的端口或停止占用进程。

### Q2: API密钥不生效
- 确保 `.env` 文件在项目根目录
- 检查密钥格式是否正确（无引号，无空格）
- 重启服务以加载新配置

### Q3: PostgreSQL 连接失败
```powershell
# 检查 PostgreSQL 服务状态
Get-Service postgresql*

# 启动服务
net start postgresql-x64-15

# 测试连接
psql -U lewis -d lewis_db -c "SELECT 1"
```

### Q4: 前端构建错误
```bash
cd frontend
rm -rf node_modules .next
npm install
npm run build
```

### Q5: 数据库连接失败
- 检查 `DATABASE_URL` 是否正确
- 确保PostgreSQL服务已启动
- 运行 `python -m lewis_ai_system.cli init-db` 初始化

## 下一步

- 📖 阅读 [DEPLOYMENT.md](DEPLOYMENT.md) 了解生产部署
- 🎨 查看 [FRONTEND_REFACTOR_SUMMARY.md](FRONTEND_REFACTOR_SUMMARY.md) 了解界面设计
- 🎬 阅读 [VIDEO_PREVIEW_GUIDE.md](VIDEO_PREVIEW_GUIDE.md) 了解视频预览功能
- 🏗️ 查看 [docs/architecture.md](docs/architecture.md) 理解系统架构

## 获取帮助

- 📋 查看 [GitHub Issues](https://github.com/yourusername/Lewis_AI_System/issues)
- 📧 联系开发团队
- 📖 阅读完整文档

---

**恭喜！** 你已经成功启动Lewis AI System。开始探索AI视频创作和智能任务执行的强大功能吧！🎉
