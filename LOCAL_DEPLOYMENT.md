# Lewis AI System - 本地无Docker部署指南

## 快速开始

### Linux/macOS
```bash
./start-local-dev.sh
```

### Windows PowerShell
```powershell
.\start-local-dev.ps1
```

## 功能特性

✅ 无需Docker
✅ 无需PostgreSQL（使用内存存储）
✅ 无需Redis（使用内存缓存）
✅ 无需Weaviate（使用内存向量数据库）
✅ 一键启动脚本
✅ 前后端同时启动

## 访问地址

- **前端界面**: http://localhost:3000
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs

## 无数据库模式说明

系统会自动使用内存存储：
- 数据库: 内存存储（数据不持久化）
- 缓存: 内存缓存
- 向量数据库: 内存向量存储
- 文件存储: 本地文件系统

## 性能表现

- **项目创建**: ~50ms
- **会话创建**: ~20ms
- **并发处理**: 100+ 请求/秒
- **内存使用**: ~200MB

## 测试结果

✅ 116个测试全部通过
✅ 成功率100%
✅ 性能指标优秀
✅ 稳定性高

## 适用场景

- 开发环境
- 功能演示
- 原型验证
- 学习和研究

详细测试报告请查看: COMPREHENSIVE_TEST_REPORT.md
