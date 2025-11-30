#!/bin/bash
echo "🚀 Lewis AI System - 前端启动脚本"
echo "=================================="

# 设置 Node.js v20 路径
export PATH="$PWD/../node-v20.18.0-linux-x64/bin:$PATH"

# 验证 Node.js 版本
echo "🔍 Node.js 版本:"
node --version

# 启动前端
echo "🚀 启动前端服务..."
npm run dev
