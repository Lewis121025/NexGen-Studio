"""
认证路由 - 提供用户登录、注册和Token管理接口
仅用于开发和内测环境
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from jose import jwt
import secrets

from ..config import settings
from ..database import db_manager, User
from ..instrumentation import get_logger
from ..auth_real import get_current_user

logger = get_logger()
router = APIRouter()

# 内存用户存储（当数据库不可用时使用）
_memory_users: dict[str, dict] = {}


def _get_memory_user(email: str) -> dict | None:
    """从内存获取用户"""
    return _memory_users.get(email)


def _create_memory_user(email: str) -> dict:
    """在内存中创建用户"""
    external_id = f"user_{secrets.token_urlsafe(16)}"
    user = {
        "external_id": external_id,
        "user_id": external_id,
        "email": email,
        "is_active": True,
        "is_admin": False,
        "credits_usd": 50.0,
        "tier": "beta",
        "last_login_at": datetime.utcnow(),
    }
    _memory_users[email] = user
    logger.info(f"新用户注册（内存）: {email} (ID: {external_id})")
    return user


def _update_memory_user_login(email: str) -> None:
    """更新内存用户最后登录时间"""
    if email in _memory_users:
        _memory_users[email]["last_login_at"] = datetime.utcnow()

# ==================== Guards ====================
def _ensure_auth_enabled() -> None:
    """Disable dev-only login/register outside dev."""
    if settings.environment == "production" or settings.auth_provider != "dev":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email/password auth is disabled for this environment. Use the configured identity provider.",
        )

def _ensure_db_ready() -> None:
    """Ensure database session factory exists before handling auth."""
    # In development mode with memory storage, we can still use auth
    # Just log a warning but don't block
    if not getattr(db_manager, "session_factory", None):
        logger.warning("数据库未初始化，认证将使用内存存储（数据不会持久化）")

# ==================== 请求/响应模型 ====================
class LoginRequest(BaseModel):
    email: EmailStr
    password: str | None = None  # 内测环境可以不需要密码


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict


# ==================== 内部函数 ====================
def create_access_token(user: User, expires_delta: timedelta | None = None) -> str:
    """创建JWT访问令牌"""
    if expires_delta is None:
        expires_delta = timedelta(hours=24 * 7)  # 7天有效期
    
    expire = datetime.utcnow() + expires_delta
    
    to_encode = {
        "sub": user.external_id,
        "email": user.email,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    
    # 使用一个简单的密钥（生产环境应该使用更安全的方式）
    secret_key = getattr(settings, "jwt_secret_key", "dev-secret-key-change-in-production")
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm="HS256")
    
    return encoded_jwt


async def get_or_create_user_by_email(email: str) -> User:
    """根据邮箱获取或创建用户"""
    _ensure_db_ready()

    # 检查是否有数据库（更严格的检查）
    has_db = getattr(db_manager, "session_factory", None) is not None

    if has_db:
        # 使用数据库
        from sqlalchemy import select

        async with db_manager.get_session() as db:
            # 查询用户
            stmt = select(User).where(User.email == email)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                # 创建新用户
                external_id = f"user_{secrets.token_urlsafe(16)}"
                user = User(
                    external_id=external_id,
                    user_id=external_id,  # 保持兼容
                    email=email,
                    is_active=True,
                    is_admin=False,
                    credits_usd=50.0,  # 内测用户赠送 $50
                    tier="beta",
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)

                logger.info(f"新用户注册: {email} (ID: {external_id})")
            else:
                # 更新最后登录时间
                user.last_login_at = datetime.utcnow()
                await db.commit()

            return user
    else:
        # 使用内存存储
        user = _get_memory_user(email)

        if not user:
            # 创建新用户
            user = _create_memory_user(email)
        else:
            # 更新最后登录时间
            _update_memory_user_login(email)

        # 返回一个类似 User 的字典对象
        class MemoryUser:
            def __init__(self, data: dict):
                self.external_id = data["external_id"]
                self.email = data["email"]
                self.is_active = data["is_active"]
                self.is_admin = data["is_admin"]
                self.credits_usd = data["credits_usd"]
                self.tier = data["tier"]
                self.last_login_at = data["last_login_at"]

        return MemoryUser(user)


# ==================== 路由 ====================
@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    _ensure_auth_enabled()
    """
    用户登录（内测简化版）
    
    - 如果用户不存在，自动注册
    - 不验证密码（仅用于内测）
    """
    try:
        user = await get_or_create_user_by_email(request.email)
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账户已被禁用"
            )
        
        # 生成访问令牌
        access_token = create_access_token(user)
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user={
                "sub": user.external_id,
                "email": user.email,
                "credits": user.credits_usd,
                "isAdmin": user.is_admin,
                "tier": user.tier,
            }
        )
    
    except Exception as e:
        logger.error(f"登录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"登录失败: {str(e)}"
        )


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    _ensure_auth_enabled()
    """
    用户注册（内测简化版）
    
    - 使用邮箱注册
    - 自动赋予内测权限
    """
    try:
        user = await get_or_create_user_by_email(request.email)
        
        # 生成访问令牌
        access_token = create_access_token(user)
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user={
                "sub": user.external_id,
                "email": user.email,
                "credits": user.credits_usd,
                "isAdmin": user.is_admin,
                "tier": user.tier,
            }
        )
    
    except Exception as e:
        logger.error(f"注册失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"注册失败: {str(e)}"
        )


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """
    获取当前用户信息
    """
    return {
        "sub": user["sub"],
        "email": user["email"],
        "credits": user["credits"],
        "isAdmin": user.get("is_admin", False),
    }


@router.post("/logout")
async def logout():
    """
    用户登出（JWT是无状态的，所以只返回成功）
    前端需要清除本地存储的Token
    """
    return {"message": "登出成功"}
