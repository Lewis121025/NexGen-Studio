#!/usr/bin/env python3
"""
ARQ Worker 启动脚本
用于处理异步任务 (视频生成、长时间计算等)
"""

import asyncio
import logging
from arq import run_worker

from nexgen_studio.task_queue import WorkerSettings
from nexgen_studio.instrumentation import get_logger

logger = get_logger()

async def startup(ctx):
    """Worker 启动时执行"""
    logger.info("🚀 Lewis AI Worker 启动中...")
    logger.info(f"Redis: {WorkerSettings.redis_settings.host}:{WorkerSettings.redis_settings.port}")
    logger.info(f"最大并发任务数: {WorkerSettings.max_jobs}")

async def shutdown(ctx):
    """Worker 关闭时执行"""
    logger.info("👋 Lewis AI Worker 正在关闭...")

# 添加生命周期钩子
WorkerSettings.on_startup = startup
WorkerSettings.on_shutdown = shutdown

if __name__ == "__main__":
    # 设置日志级别
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    
    logger.info("=" * 60)
    logger.info("Lewis AI System - Async Task Worker")
    logger.info("=" * 60)
    
    # 运行 Worker
    run_worker(WorkerSettings)
