"""FastAPI 应用程序入口点。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from .config import settings
from .versioning import version_middleware
from .routers.versioned import (
    v1_router,
    v2_router,
    legacy_router,
    get_all_versions_info,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """管理应用程序生命周期。"""
    # 启动
    from .instrumentation import get_logger
    logger = get_logger()
    logger.info(f"正在启动 Lewis AI 系统 ({settings.environment})")
    
    # 如果配置了数据库，则初始化数据库
    if settings.database_url:
        from .database import init_database
        try:
            await init_database()
            logger.info("数据库初始化成功")
            # 将创意存储库重新绑定到基于数据库的实现
            from .creative import repository as creative_repo_module
            creative_repo_module.creative_repository = creative_repo_module.DatabaseCreativeProjectRepository()
            from .creative import workflow as creative_workflow_module
            creative_workflow_module.creative_orchestrator = creative_workflow_module.CreativeOrchestrator(
                repository=creative_repo_module.creative_repository
            )
            from .routers import creative as creative_router_module
            creative_router_module.creative_repository = creative_repo_module.creative_repository
            creative_router_module.creative_orchestrator = creative_workflow_module.creative_orchestrator
            logger.info("创意存储库已切换到数据库后端")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}", exc_info=True)
            logger.warning("数据库初始化失败，应用将继续使用内存存储启动")
    else:
        logger.info("未配置数据库; 使用内存存储")
    
    # 初始化 Redis 缓存
    if settings.redis_enabled:
        from .redis_cache import cache_manager
        try:
            await cache_manager.initialize()
            logger.info("Redis 缓存已初始化")
        except Exception as e:
            logger.warning(f"Redis 初始化失败: {e}")
    
    # 初始化向量数据库
    try:
        from .vector_db import vector_db
        vector_db.initialize()
        logger.info("向量数据库已初始化")
    except Exception as e:
        logger.warning(f"向量数据库初始化失败: {e}")
    
    # 初始化 S3 存储
    from .s3_storage import s3_storage
    if s3_storage.is_available():
        logger.info("S3 存储已配置")
    else:
        logger.warning("S3 存储未配置，使用本地回退")
    
    yield
    
    # 关闭
    logger.info("正在关闭 Lewis AI 系统")
    if settings.database_url:
        from .database import db_manager
        await db_manager.close()
    
    # 关闭 Redis 缓存
    if settings.redis_enabled:
        from .redis_cache import cache_manager
        await cache_manager.close()
    
    # 关闭向量数据库
    from .vector_db import vector_db
    await vector_db.close()


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    lifespan=lifespan,
)

# API 版本中间件
app.middleware("http")(version_middleware)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 受信任的主机中间件 (生产安全)
if settings.environment == "production":
    hosts = [host.strip() for host in settings.trusted_hosts]
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=hosts or ["*"],
    )

# 包含路由 - 只包含版本化路由，避免重复注册
# 基本API路由通过版本化路由提供

# 版本化 API 路由
app.include_router(v1_router)   # /v1/*
app.include_router(v2_router)   # /v2/*
app.include_router(legacy_router)  # 兼容旧版本


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理程序，确保 JSON 响应。"""
    from fastapi.responses import JSONResponse
    from .instrumentation import get_logger
    import traceback
    
    logger = get_logger()
    logger.error(f"未处理的异常在 {request.method} {request.url.path}: {exc}", exc_info=True)
    
    # 在开发环境中始终包含回溯，在生产环境中包含错误详细信息
    env = settings.environment
    if env != "production":
        traceback_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        return JSONResponse(
            status_code=500,
            content={
                "detail": "内部服务器错误",
                "error": str(exc),
                "error_type": type(exc).__name__,
                "traceback": traceback_str,
                "path": str(request.url.path),
            },
        )
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "内部服务器错误",
            "error": str(exc),
            "error_type": type(exc).__name__,
        },
    )


@app.get("/")
async def root():
    """基本服务元数据。"""
    return {
        "message": "Lewis AI System API",
        "version": settings.api_version,
        "docs": "/docs",
    }


@app.get("/api/versions")
async def list_api_versions() -> dict[str, Any]:
    """列出所有可用的 API 版本信息。"""
    return get_all_versions_info()


@app.get("/healthz")
async def healthcheck() -> dict[str, str]:
    """健康检查端点。"""
    return {"status": "ok", "environment": settings.environment}


@app.get("/readyz")
async def readiness_check() -> dict[str, str]:
    """容器编排的就绪检查。"""
    checks = {
        "status": "ready",
        "database": "not_configured",
        "s3": "not_configured",
    }
    
    # 检查数据库
    if settings.database_url:
        try:
            from .database import db_manager
            if db_manager.engine:
                checks["database"] = "connected"
            else:
                checks["database"] = "not_initialized"
        except Exception:
            checks["database"] = "error"
    
    # 检查 S3
    from .s3_storage import s3_storage
    if s3_storage.is_available():
        checks["s3"] = "configured"
    
    return checks
