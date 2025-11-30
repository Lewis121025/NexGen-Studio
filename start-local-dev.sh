#!/usr/bin/env bash
# Lewis AI System - 本地开发启动脚本（无需Docker）

set -euo pipefail

echo "=========================================="
echo "  Lewis AI System - 本地开发模式"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误：未找到 python3${NC}"
    echo "请安装 Python 3.11 或更高版本"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}错误：Python版本过低 ($PYTHON_VERSION)${NC}"
    echo "需要 Python $REQUIRED_VERSION 或更高版本"
    exit 1
fi

echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION"

# 检查Node.js
if ! command -v node &> /dev/null; then
    echo -e "${YELLOW}警告：未找到 Node.js${NC}"
    echo "如果需要开发前端，请安装 Node.js 18+"
else
    NODE_VERSION=$(node --version)
    echo -e "${GREEN}✓${NC} Node.js $NODE_VERSION"
fi

# 检查.env文件
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}警告：未找到 .env 文件${NC}"
    echo "复制示例配置..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}✓${NC} 已创建 .env 文件"
        echo "请编辑 .env 文件并填入必要的API密钥"
    else
        echo -e "${RED}错误：未找到 .env.example 文件${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓${NC} 找到 .env 配置文件"
fi

# 安装后端依赖
echo ""
echo "📦 检查Python依赖..."
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q -e ".[dev]" 2>/dev/null || pip install -q -e .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} 后端依赖已安装"
else
    echo -e "${RED}✗${NC} 依赖安装失败"
    exit 1
fi

# 安装前端依赖
if [ -d "frontend" ]; then
    echo ""
    echo "📦 检查前端依赖..."
    cd frontend

    if [ ! -d "node_modules" ]; then
        echo "安装前端依赖..."
        npm install > /dev/null 2>&1
    fi

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} 前端依赖已安装"
    else
        echo -e "${YELLOW}警告：前端依赖安装失败${NC}"
        echo "您可以稍后手动运行：cd frontend && npm install"
    fi

    cd ..
fi

# 启动应用
echo ""
echo "🚀 启动应用..."
echo ""

# 检查端口是否被占用
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}警告：端口8000已被占用${NC}"
    echo "请关闭占用端口的进程或修改端口配置"
fi

# 启动后端
echo -e "${GREEN}启动后端服务...${NC}"
echo "后端地址: http://localhost:8000"
echo "API文档: http://localhost:8000/docs"
echo ""

# 使用后台运行
python3 -m uvicorn lewis_ai_system.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    &
BACKEND_PID=$!

# 等待后端启动
sleep 3

# 检查后端是否启动成功
if curl -s http://localhost:8000/healthz > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} 后端服务启动成功！"
else
    echo -e "${RED}✗${NC} 后端服务启动失败"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

# 启动前端（如果已安装依赖）
if [ -d "frontend" ] && [ -d "frontend/node_modules" ]; then
    echo ""
    echo -e "${GREEN}启动前端服务...${NC}"
    echo "前端地址: http://localhost:3000"
    echo ""

    cd frontend
    npm run dev &
    FRONTEND_PID=$!
    cd ..

    # 等待前端启动
    sleep 5

    # 检查前端是否启动成功
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} 前端服务启动成功！"
    else
        echo -e "${YELLOW}警告：前端服务启动失败${NC}"
        echo "您可以稍后手动运行：cd frontend && npm run dev"
    fi
fi

echo ""
echo "=========================================="
echo -e "${GREEN}🎉 Lewis AI System 已启动！${NC}"
echo "=========================================="
echo ""
echo "访问地址："
echo "  前端界面: http://localhost:3000"
echo "  后端API:  http://localhost:8000"
echo "  API文档:  http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

# 等待用户中断
trap "echo ''; echo '正在停止服务...'; kill $BACKEND_PID 2>/dev/null || true; [ -n '${FRONTEND_PID:-}' ] && kill $FRONTEND_PID 2>/dev/null || true; echo '服务已停止'; exit 0" INT

# 保持脚本运行
wait
