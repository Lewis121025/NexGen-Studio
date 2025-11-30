"""版本化路由器模块。

提供不同版本的 API 路由。
"""

from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, HTTPException, status

from ..versioning import version_manager, create_version_response
from .creative import router as creative_router
from .general import router as general_router
from .governance import router as governance_router
from .auth import router as auth_router


def create_v1_router() -> APIRouter:
    """创建 v1 API 路由器。
    
    Returns:
        v1 版本的路由器
    """
    router = APIRouter(prefix="/v1", tags=["v1"])
    
    # 包含基本路由，但避免重复
    router.include_router(creative_router, prefix="/creative")
    router.include_router(general_router, prefix="/general") 
    router.include_router(governance_router, prefix="/governance")
    router.include_router(auth_router, prefix="/auth")
    
    @router.get("/info")
    async def v1_info():
        """v1 API 信息。"""
        return create_version_response("v1", {
            "version": "1.0",
            "status": "stable",
            "features": [
                "creative_mode",
                "general_mode", 
                "quality_control",
                "cost_monitoring",
                "user_authentication"
            ],
            "deprecated_features": [],
            "migration_guide": None
        })
    
    @router.get("/health")
    async def v1_health():
        """v1 API 健康检查。"""
        return create_version_response("v1", {
            "status": "healthy",
            "version": "v1",
            "timestamp": "2025-11-27T08:55:00Z"
        })
    
    return router


def create_v2_router() -> APIRouter:
    """创建 v2 API 路由器。
    
    Returns:
        v2 版本的路由器
    """
    router = APIRouter(prefix="/v2", tags=["v2"])  # 修正为一致的格式
    
    # V2 包含增强功能
    @router.get("/info")
    async def v2_info():
        """v2 API 信息。"""
        return create_version_response("v2", {
            "version": "2.0",
            "status": "beta",
            "features": [
                "creative_mode_v2",
                "general_mode_v2",
                "enhanced_quality_control",
                "real_time_cost_tracking",
                "advanced_authentication",
                "batch_processing",
                "consistency_control",
                "api_rate_limiting"
            ],
            "deprecated_features": [
                "legacy_image_generation"
            ],
            "migration_guide": {
                "from_v1": {
                    "breaking_changes": [
                        "Request/response format changes",
                        "Authentication header updates",
                        "Cost tracking API modifications"
                    ],
                    "recommended_actions": [
                        "Update client libraries",
                        "Migrate authentication flow",
                        "Test new endpoints"
                    ]
                }
            }
        })
    
    @router.get("/health")
    async def v2_health():
        """v2 API 健康检查。"""
        return create_version_response("v2", {
            "status": "healthy",
            "version": "v2",
            "timestamp": "2025-11-27T08:55:00Z",
            "beta_features": [
                "enhanced_consistency_engine",
                "real_time_collaboration"
            ]
        })
    
    # V2 新增的路由示例
    @router.get("/features")
    async def v2_features():
        """获取 V2 功能列表。"""
        return create_version_response("v2", {
            "available_features": {
                "creative": {
                    "enhanced_script_generation": True,
                    "multi_style_support": True,
                    "real_time_collaboration": False,
                    "batch_processing": True
                },
                "quality": {
                    "advanced_consistency_check": True,
                    "custom_qc_rules": True,
                    "real_time_monitoring": True
                },
                "governance": {
                    "enhanced_cost_tracking": True,
                    "usage_analytics": True,
                    "alert_system": True
                }
            }
        })
    
    return router


def create_legacy_router() -> APIRouter:
    """创建旧版 API 路由器（向后兼容）。
    
    Returns:
        旧版兼容路由器
    """
    router = APIRouter(prefix="/api", tags=["legacy"])
    
    @router.get("/version")
    async def legacy_version():
        """旧版版本信息。"""
        return {
            "version": "legacy",
            "message": "This is the legacy API. Please migrate to v1 or v2.",
            "migration_urls": {
                "v1": "/api/v1/info",
                "v2": "/api/v2/info"
            },
            "deprecation_date": "2025-12-31",
            "sunset_date": "2026-06-30"
        }
    
    # 重定向旧版路由到新版
    @router.api_route("/creative/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def legacy_creative_redirect():
        """旧版创作路由重定向。"""
        raise HTTPException(
            status_code=status.HTTP_301_MOVED_PERMANENTLY,
            detail={
                "message": "Legacy creative API has been moved",
                "new_location": "/api/v1/creative",
                "migration_required": True
            }
        )
    
    return router


# 注册所有版本，只实例化一次以避免重复路由
v1_router = create_v1_router()
v2_router = create_v2_router()
legacy_router = create_legacy_router()

version_manager.register_version("v1", v1_router)
version_manager.register_version("v2", v2_router)
version_manager.register_version(
    "legacy",
    legacy_router,
    deprecated=True,
    deprecation_message="Please migrate to v1 or v2 API",
)


def get_all_versions_info() -> Dict[str, Any]:
    """获取所有版本信息。
    
    Returns:
        所有版本的详细信息
    """
    return {
        "current_versions": version_manager.supported_versions,
        "default_version": version_manager.default_version,
        "deprecated_versions": version_manager.deprecated_versions,
        "version_details": {
            version: version_manager.get_version_info(version)
            for version in version_manager.supported_versions + list(version_manager.deprecated_versions.keys())
        },
        "migration_matrix": {
            "legacy_to_v1": {
                "effort": "low",
                "breaking_changes": False,
                "guide": "Update base URL from /api to /api/v1"
            },
            "v1_to_v2": {
                "effort": "medium", 
                "breaking_changes": True,
                "guide": "Update request/response formats and authentication"
            }
        }
    }