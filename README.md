# NexGen Studio

🎬 **AI-Powered Video Generation & Intelligent Assistant Platform**

NexGen Studio 是一个双模式 AI 编排平台，提供创意视频生成和通用任务自动化的结构化工作流。

## ✨ 核心功能

### 🎥 Creative Mode - 视频生成工作流
- **智能脚本生成**: AI 根据简报自动生成分镜脚本
- **分镜图片生成**: 使用豆包 Seedream 生成高质量分镜图
- **视频渲染**: 支持豆包 Seedance、Runway、Pika 等视频生成引擎
- **完整工作流**: 概念 → 脚本 → 分镜 → 渲染 → 完成

### 💬 General Mode - 智能助手
- **ReAct 推理循环**: 思考-行动-观察的智能决策
- **工具调用**: 支持 Google 搜索、Python 沙箱等
- **对话记忆**: 向量数据库支持的长期记忆
- **流式响应**: 实时返回推理过程

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Next.js 14, React 18, TailwindCSS, Zustand |
| 后端 | FastAPI, SQLAlchemy, Pydantic |
| AI | OpenAI GPT-4o, 豆包 Doubao API |
| 数据库 | PostgreSQL, Redis, Weaviate |
| 部署 | Docker Compose |

## 🚀 快速开始

### 环境要求
- Docker & Docker Compose
- Node.js 18+ (开发模式)
- Python 3.11+ (开发模式)

### 启动服务

```bash
# 克隆项目
git clone https://github.com/Lewis121025/NexGen-Studio.git
cd NexGen-Studio

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API Keys

# 启动所有服务
docker compose up -d

# 访问
# 前端: http://localhost:3000
# API: http://localhost:8000
```

### 开发模式

```bash
# 启动数据库服务
docker compose up -d postgres redis weaviate

# 启动后端
cd src && uvicorn nexgen_studio.main:app --reload --port 8000

# 启动前端
cd frontend && npm install && npm run dev
```

## 📁 项目结构

```
NexGen-Studio/
├── src/nexgen_studio/     # 后端 Python 代码
│   ├── agents.py          # AI Agent 实现
│   ├── providers.py       # 视频/图片生成提供商
│   ├── creative/          # Creative 模式模块
│   ├── general/           # General 模式模块
│   └── routers/           # API 路由
├── frontend/              # Next.js 前端
│   ├── src/app/          # 页面
│   ├── src/components/   # 组件
│   └── src/lib/          # 工具库和状态管理
├── docker-compose.yml     # Docker 编排
└── tests/                 # 测试用例
```

## 🔑 环境变量

```env
# AI 服务
OPENAI_API_KEY=sk-xxx
ARK_API_KEY=xxx              # 豆包 API

# 数据库
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/nexgen
REDIS_URL=redis://localhost:6379

# 可选
GOOGLE_API_KEY=xxx           # Google 搜索
WEAVIATE_HOST=localhost:8080 # 向量数据库
```

## 📖 API 文档

启动后访问: http://localhost:8000/docs

## 🎯 路线图

- [x] Creative Mode 视频生成流程
- [x] General Mode 对话助手
- [x] Docker 部署支持
- [ ] 用户认证系统
- [ ] 多租户支持
- [ ] 视频编辑功能

## 📄 License

MIT License

---

**NexGen Studio** - *Next Generation AI Creative Studio*
