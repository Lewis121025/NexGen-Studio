"""API 版本控制模块。

提供 API 版本管理和路由功能。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse


class APIVersionManager:
    """API 版本管理器。
    
    负责管理不同版本的 API 路由和兼容性。
    """
    
    def __init__(self) -> None:
        """初始化版本管理器。"""
        self.versions: Dict[str, APIRouter] = {}
        self.default_version = "v1"
        self.supported_versions = [self.default_version]
        self.deprecated_versions: Dict[str, str] = {}  # version -> deprecation_message
        
    def register_version(self, version: str, router: APIRouter, deprecated: bool = False, deprecation_message: str = "") -> None:
        """注册 API 版本。
        
        Args:
            version: 版本号 (如 "v1", "v2")
            router: FastAPI 路由器
            deprecated: 是否已弃用
            deprecation_message: 弃用消息
        """
        self.versions[version] = router
        if not deprecated and version not in self.supported_versions:
            self.supported_versions.append(version)
        if deprecated:
            self.deprecated_versions[version] = deprecation_message
    
    def get_version_router(self, version: str) -> APIRouter:
        """获取指定版本的路由器。
        
        Args:
            version: 版本号
            
        Returns:
            对应的路由器
            
        Raises:
            HTTPException: 版本不支持时
        """
        if version not in self.versions:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "API version not supported",
                    "supported_versions": self.supported_versions,
                    "default_version": self.default_version
                }
            )
        return self.versions[version]
    
    def get_version_info(self, version: str) -> Dict[str, Any]:
        """获取版本信息。
        
        Args:
            version: 版本号
            
        Returns:
            版本信息字典
        """
        return {
            "version": version,
            "is_supported": version in self.supported_versions,
            "is_deprecated": version in self.deprecated_versions,
            "deprecation_message": self.deprecated_versions.get(version, ""),
            "is_default": version == self.default_version
        }


# 全局版本管理器实例
version_manager = APIVersionManager()


def create_versioned_router(prefix: str, version: str) -> APIRouter:
    """创建版本化路由器。
    
    Args:
        prefix: 路由前缀
        version: 版本号
        
    Returns:
        版本化的路由器
    """
    router = APIRouter(prefix=f"/{version}{prefix}")
    return router


async def version_middleware(request: Request, call_next):
    """版本控制中间件。
    
    从 URL 路径或请求头中提取 API 版本。
    """
    path = request.url.path
    
    # 从 URL 路径提取版本
    if path.startswith("/api/"):
        path_parts = path.split("/")
        if len(path_parts) >= 3 and path_parts[2].startswith("v"):
            version = path_parts[2]
            request.state.api_version = version
        else:
            request.state.api_version = version_manager.default_version
    else:
        request.state.api_version = version_manager.default_version
    
    # 从请求头提取版本（优先级更高）
    api_version_header = request.headers.get("API-Version")
    if api_version_header:
        request.state.api_version = api_version_header
    
    response = await call_next(request)
    
    # 添加版本信息到响应头
    response.headers["API-Version"] = request.state.api_version
    response.headers["Supported-Versions"] = ",".join(version_manager.supported_versions)
    
    # 如果是弃用版本，添加警告头
    if request.state.api_version in version_manager.deprecated_versions:
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = version_manager.deprecated_versions[request.state.api_version]
    
    return response


def create_version_response(version: str, data: Any) -> JSONResponse:
    """创建版本化响应。
    
    Args:
        version: API 版本
        data: 响应数据
        
    Returns:
        包含版本信息的 JSON 响应
    """
    return JSONResponse(
        content={
            "data": data,
            "meta": {
                "api_version": version,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "version_info": version_manager.get_version_info(version)
            }
        }
    )


def validate_api_version(version: str) -> None:
    """验证 API 版本。
    
    Args:
        version: 要验证的版本号
        
    Raises:
        HTTPException: 版本无效时
    """
    if version not in version_manager.supported_versions:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid API version",
                "message": f"Version '{version}' is not supported",
                "supported_versions": version_manager.supported_versions,
                "default_version": version_manager.default_version
            }
        )