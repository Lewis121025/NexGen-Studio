"""Authentication and authorization utilities."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# API Key bearer authentication
required_bearer = HTTPBearer()
optional_bearer = HTTPBearer(auto_error=False)
API_KEY_PREFIX = "lewis_"


def _configured_api_key_hashes() -> set[str]:
    """Return hashed API keys loaded from settings."""
    keys = getattr(settings, "service_api_keys", [])
    return {hash_api_key(key) for key in keys if isinstance(key, str) and key}


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key and its hash.
    
    Returns:
        tuple: (plain_key, hashed_key)
    """
    plain_key = f"lewis_{secrets.token_urlsafe(32)}"
    hashed_key = hash_api_key(plain_key)
    return plain_key, hashed_key


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage."""
    salted = f"{api_key}{settings.api_key_salt}"
    return hashlib.sha256(salted.encode()).hexdigest()


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """Verify an API key against a hash."""
    return hash_api_key(plain_key) == hashed_key


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT access token."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(required_bearer)) -> dict:
    """FastAPI dependency to get current authenticated user.
    
    Supports both JWT tokens and API keys.
    """
    token = credentials.credentials
    
    # Try JWT token first
    if not token.startswith(API_KEY_PREFIX):
        try:
            payload = decode_access_token(token)
            user_id = payload.get("sub")
            if user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token",
                )
            return {"user_id": user_id, "auth_type": "jwt"}
        except HTTPException:
            pass
    
    # Try API key
    # In production, this should query the database
    # For now, we'll accept any key starting with "lewis_"
    if token.startswith(API_KEY_PREFIX):
        hashed = hash_api_key(token)
        if hashed not in _configured_api_key_hashes():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = f"user_{hashed[:12]}"
        return {"user_id": user_id, "auth_type": "api_key"}
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(optional_bearer)
) -> Optional[dict]:
    """Optional authentication - returns None if no credentials provided."""
    if credentials is None:
        return None
    return await get_current_user(credentials)


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self._requests: dict[str, list[datetime]] = {}
    
    def check_rate_limit(self, user_id: str) -> bool:
        """Check if user is within rate limit.
        
        Returns:
            bool: True if within limit, False if exceeded
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=1)
        
        # Get user's recent requests
        if user_id not in self._requests:
            self._requests[user_id] = []
        
        # Remove old requests
        self._requests[user_id] = [
            req_time for req_time in self._requests[user_id]
            if req_time > cutoff
        ]
        
        # Check limit
        if len(self._requests[user_id]) >= self.requests_per_minute:
            return False
        
        # Record this request
        self._requests[user_id].append(now)
        return True
    
    def cleanup_old_entries(self):
        """Remove entries older than 1 minute."""
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=1)
        
        for user_id in list(self._requests.keys()):
            self._requests[user_id] = [
                req_time for req_time in self._requests[user_id]
                if req_time > cutoff
            ]
            
            if not self._requests[user_id]:
                del self._requests[user_id]


# Global rate limiter instance
rate_limiter = RateLimiter(requests_per_minute=settings.rate_limit_per_minute)


async def check_rate_limit(user: dict = Security(get_current_user)):
    """FastAPI dependency for rate limiting."""
    if not settings.rate_limit_enabled:
        return user
    
    user_id = user["user_id"]
    if not rate_limiter.check_rate_limit(user_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
        )
    
    return user
