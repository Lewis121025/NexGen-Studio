#!/bin/bash
echo "正在停止 Lewis AI System 服务..."
echo ""

# 停止后端服务
if pkill -f "uvicorn lewis_ai_system.main:app"; then
    echo "✅ 后端服务已停止"
else
    echo "ℹ️  后端服务未运行"
fi

# 停止前端服务
if pkill -f "next dev"; then
    echo "✅ 前端服务已停止"
else
    echo "ℹ️  前端服务未运行"
fi

echo ""
echo "所有服务已停止"
