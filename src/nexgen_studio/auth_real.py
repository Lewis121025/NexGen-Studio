"""
真实的 JWT 鉴权实现 - 集成 Clerk / Auth0
废弃硬编码的 API_KEY_PREFIX 检查
"""

from __future__ import annotations

import httpx
from typing import Optional
from datetime import datetime, timedelta

from fastapi import HTTPException, Security, status, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt, jwk
from jose.utils import base64url_decode

from .config import settings
from .instrumentation import get_logger
from .database import db_manager, User

logger = get_logger()

# HTTP Bearer Token 验证器
bearer_scheme = HTTPBearer()


# ==================== JWT 验证 (Clerk / Auth0) ====================
class JWTValidator:
    """JWT Token 验证器 (支持 Clerk 和 Auth0)"""
    
    def __init__(self, provider: str = "clerk"):
        """
        Args:
            provider: "clerk" 或 "auth0"
        """
        self.provider = provider
        self._jwks_cache: dict | None = None
        self._cache_expiry: datetime | None = None
    
    async def get_jwks(self) -> dict:
        """获取 JWKS (JSON Web Key Set) - 用于验证 JWT 签名"""
        # 检查缓存
        if self._jwks_cache and self._cache_expiry and datetime.utcnow() < self._cache_expiry:
            return self._jwks_cache
        
        # 根据 Provider 获取 JWKS URL
        if self.provider == "clerk":
            # Clerk JWKS URL 格式: https://clerk.{your-domain}.com/.well-known/jwks.json
            jwks_url = getattr(settings, "clerk_jwks_url", None)
            if not jwks_url:
                raise RuntimeError("CLERK_JWKS_URL 未配置! 示例: https://clerk.example.com/.well-known/jwks.json")
        
        elif self.provider == "auth0":
            # Auth0 JWKS URL 格式: https://{tenant}.auth0.com/.well-known/jwks.json
            auth0_domain = getattr(settings, "auth0_domain", None)
            if not auth0_domain:
                raise RuntimeError("AUTH0_DOMAIN 未配置! 示例: your-tenant.auth0.com")
            jwks_url = f"https://{auth0_domain}/.well-known/jwks.json"
        
        else:
            raise ValueError(f"不支持的 Provider: {self.provider}")
        
        # 下载 JWKS
        async with httpx.AsyncClient() as client:
            response = await client.get(jwks_url, timeout=10.0)
            response.raise_for_status()
            jwks = response.json()
        
        # 缓存 1 小时
        self._jwks_cache = jwks
        self._cache_expiry = datetime.utcnow() + timedelta(hours=1)
        
        logger.info(f"JWKS 已更新 (Provider: {self.provider})")
        
        return jwks
    
    async def verify_token(self, token: str) -> dict:
        """
        验证 JWT Token
        
        Returns:
            User claims (包含 sub, email, etc.)
        
        Raises:
            HTTPException: Token 无效或过期
        """
        try:
            # 1. 解码 Token Header (不验证签名)
            header = jwt.get_unverified_header(token)
            
            # 2. 获取 JWKS
            jwks = await self.get_jwks()
            
            # 3. 找到对应的公钥
            key_id = header.get("kid")
            if not key_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token 缺少 kid (Key ID)"
                )
            
            # 在 JWKS 中查找对应的 Key
            keys = {k["kid"]: k for k in jwks.get("keys", [])}
            if key_id not in keys:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token 签名密钥无效"
                )
            
            # 4. 验证签名并解码
            public_key = jwk.construct(keys[key_id])
            
            # Clerk: 不需要 audience, Auth0: 需要 audience
            audience = getattr(settings, "auth0_audience", None) if self.provider == "auth0" else None
            
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=audience,
            )
            
            # 5. 检查必要的 Claims
            if "sub" not in payload:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token 缺少 sub (User ID)"
                )
            
            logger.debug(f"JWT 验证成功: sub={payload['sub']}")
            
            return payload
        
        except JWTError as e:
            logger.warning(f"JWT 验证失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"无效的认证 Token: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e


# 全局验证器实例
jwt_validator = JWTValidator(
    provider=getattr(settings, "auth_provider", "clerk")  # "clerk" 或 "auth0"
)


# ==================== FastAPI 依赖项 ====================
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)
) -> dict:
    """
    获取当前登录用户 (必须登录)
    
    Returns:
        {
            "sub": str,           # 用户唯一标识 (Clerk User ID 或 Auth0 sub)
            "email": str,         # 用户邮箱
            "credits": float,     # 用户余额
            ...
        }
    """
    token = credentials.credentials
    
    # 1. 验证 JWT Token
    claims = await jwt_validator.verify_token(token)
    
    # 2. 从数据库加载用户信息 (包含 credits 余额)
    user = await _get_or_create_user(claims["sub"], claims.get("email"))
    
    return {
        "sub": user.external_id,
        "email": user.email,
        "credits": user.credits_usd,
        "is_admin": user.is_admin,
        "jwt_claims": claims,  # 原始 JWT Claims
    }


async def _get_or_create_user(sub: str, email: str | None = None) -> User:
    """从数据库获取用户,不存在则自动创建"""
    async with db_manager.get_session() as db:
        from sqlalchemy import select
        
        # 查询用户
        stmt = select(User).where(User.external_id == sub)
        user = await db.scalar(stmt)
        
        if not user:
            # 首次登录,创建用户记录
            user = User(
                external_id=sub,
                email=email or f"{sub}@unknown.com",
                credits_usd=10.0,  # 新用户赠送 $10
                is_admin=False,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            
            logger.info(f"新用户注册: sub={sub}, email={email}, credits=$10")
        
        return user


async def check_credits(user: dict = Depends(get_current_user), required_credits: float = 0.1):
    """
    检查用户余额是否充足
    
    Args:
        user: 当前用户
        required_credits: 所需余额
    
    Raises:
        HTTPException: 余额不足
    """
    if user["credits"] < required_credits:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"余额不足! 需要 ${required_credits:.2f}, 当前余额 ${user['credits']:.2f}"
        )
    
    return user


async def require_admin(user: dict = Depends(get_current_user)):
    """要求管理员权限"""
    if not user.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    
    return user


# ==================== 使用示例 ====================
"""
# 1. 在 Router 中使用

from .auth_real import get_current_user, check_credits

@router.post("/creative/projects")
async def create_project(
    payload: CreateProjectRequest,
    user: dict = Depends(get_current_user),  # 强制登录
):
    # user["sub"] 是用户 ID
    # user["credits"] 是余额
    ...

@router.post("/creative/projects/{id}/generate")
async def generate_video(
    project_id: str,
    user: dict = Depends(check_credits)  # 检查余额 >= $0.1
):
    # 扣费
    await deduct_credits(user["sub"], 5.0)
    ...


# 2. 配置环境变量 (.env)

# Clerk
AUTH_PROVIDER=clerk
CLERK_JWKS_URL=https://clerk.your-app.com/.well-known/jwks.json

# Auth0
AUTH_PROVIDER=auth0
AUTH0_DOMAIN=your-tenant.auth0.com
AUTH0_AUDIENCE=https://api.your-app.com
"""
