"""Redis cache integration for session data, rate limiting, and caching."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from .config import settings
from .instrumentation import get_logger

logger = get_logger()


class RedisCache:
    """Redis cache manager for distributed caching and rate limiting."""
    
    def __init__(self, url: str | None = None):
        self.url = url or "redis://localhost:6379/0"
        self.client: Any = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize Redis connection."""
        if self._initialized:
            return
        
        if not REDIS_AVAILABLE:
            logger.warning("redis package not installed, caching disabled")
            return
        
        try:
            self.client = await redis.from_url(
                self.url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5
            )
            await self.client.ping()
            logger.info("Redis cache initialized")
            self._initialized = True
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}, caching disabled")
            self.client = None
    
    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        if not self.client:
            return None
        
        try:
            value = await self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Redis get failed: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> bool:
        """Set value in cache with optional TTL."""
        if not self.client:
            return False
        
        try:
            serialized = json.dumps(value)
            if ttl_seconds:
                await self.client.setex(key, ttl_seconds, serialized)
            else:
                await self.client.set(key, serialized)
            return True
        except Exception as e:
            logger.error(f"Redis set failed: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.client:
            return False
        
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete failed: {e}")
            return False
    
    async def increment(self, key: str, amount: int = 1) -> int | None:
        """Increment a counter."""
        if not self.client:
            return None
        
        try:
            return await self.client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Redis increment failed: {e}")
            return None
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on a key."""
        if not self.client:
            return False
        
        try:
            await self.client.expire(key, seconds)
            return True
        except Exception as e:
            logger.error(f"Redis expire failed: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self.client:
            return False
        
        try:
            return bool(await self.client.exists(key))
        except Exception as e:
            logger.error(f"Redis exists failed: {e}")
            return False
    
    async def rate_limit_check(
        self, 
        identifier: str, 
        max_requests: int, 
        window_seconds: int
    ) -> tuple[bool, int]:
        """
        Check rate limit using sliding window.
        
        Returns:
            (allowed, remaining_requests)
        """
        if not self.client:
            return True, max_requests  # Allow if Redis unavailable
        
        key = f"ratelimit:{identifier}"
        
        try:
            # Use Redis pipeline for atomic operations
            pipe = self.client.pipeline()
            current = await self.client.get(key)
            
            if current is None:
                # First request in window
                await self.client.setex(key, window_seconds, "1")
                return True, max_requests - 1
            
            count = int(current)
            if count >= max_requests:
                return False, 0
            
            # Increment and maintain TTL
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            await pipe.execute()
            
            return True, max_requests - count - 1
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return True, max_requests  # Fail open
    
    async def cache_tool_result(
        self, 
        tool_name: str, 
        params_hash: str, 
        result: Any,
        ttl_seconds: int = 3600
    ) -> bool:
        """Cache tool execution result."""
        key = f"tool:{tool_name}:{params_hash}"
        return await self.set(key, result, ttl_seconds)
    
    async def get_cached_tool_result(
        self, 
        tool_name: str, 
        params_hash: str
    ) -> Any | None:
        """Get cached tool result."""
        key = f"tool:{tool_name}:{params_hash}"
        return await self.get(key)
    
    async def store_session_state(
        self,
        session_id: str,
        state: dict[str, Any],
        ttl_seconds: int = 86400  # 24 hours
    ) -> bool:
        """Store session state."""
        key = f"session:{session_id}"
        return await self.set(key, state, ttl_seconds)
    
    async def get_session_state(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve session state."""
        key = f"session:{session_id}"
        return await self.get(key)
    
    async def lock_acquire(
        self, 
        lock_name: str, 
        timeout_seconds: int = 10,
        owner: str = "default"
    ) -> bool:
        """Acquire a distributed lock."""
        if not self.client:
            return True  # Allow if Redis unavailable
        
        key = f"lock:{lock_name}"
        try:
            # NX = only set if not exists, EX = expire in seconds
            result = await self.client.set(key, owner, nx=True, ex=timeout_seconds)
            return bool(result)
        except Exception as e:
            logger.error(f"Lock acquire failed: {e}")
            return False
    
    async def lock_release(self, lock_name: str, owner: str = "default") -> bool:
        """Release a distributed lock."""
        if not self.client:
            return True
        
        key = f"lock:{lock_name}"
        try:
            # Only delete if we own the lock
            current_owner = await self.client.get(key)
            if current_owner == owner:
                await self.client.delete(key)
                return True
            return False
        except Exception as e:
            logger.error(f"Lock release failed: {e}")
            return False
    
    async def publish(self, channel: str, message: str) -> int:
        """Publish message to a channel."""
        if not self.client:
            return 0
        
        try:
            return await self.client.publish(channel, message)
        except Exception as e:
            logger.error(f"Redis publish failed: {e}")
            return 0
    
    async def close(self):
        """Close Redis connection."""
        if self.client:
            await self.client.close()
            logger.info("Redis connection closed")


class InMemoryCache:
    """Fallback in-memory cache when Redis is unavailable."""
    
    def __init__(self):
        self._store: dict[str, tuple[Any, float | None]] = {}
        self._rate_limits: dict[str, tuple[int, float]] = {}
    
    async def initialize(self):
        """No-op for in-memory."""
        pass
    
    async def get(self, key: str) -> Any | None:
        """Get value from memory cache."""
        import time
        
        if key not in self._store:
            return None
        
        value, expiry = self._store[key]
        if expiry and time.time() > expiry:
            del self._store[key]
            return None
        
        return value
    
    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> bool:
        """Set value in memory cache."""
        import time
        
        expiry = time.time() + ttl_seconds if ttl_seconds else None
        self._store[key] = (value, expiry)
        return True
    
    async def delete(self, key: str) -> bool:
        """Delete key from memory."""
        self._store.pop(key, None)
        return True
    
    async def rate_limit_check(
        self, 
        identifier: str, 
        max_requests: int, 
        window_seconds: int
    ) -> tuple[bool, int]:
        """Simple in-memory rate limiting."""
        import time
        
        now = time.time()
        
        if identifier in self._rate_limits:
            count, window_start = self._rate_limits[identifier]
            
            if now - window_start > window_seconds:
                # Reset window
                self._rate_limits[identifier] = (1, now)
                return True, max_requests - 1
            
            if count >= max_requests:
                return False, 0
            
            self._rate_limits[identifier] = (count + 1, window_start)
            return True, max_requests - count - 1
        
        self._rate_limits[identifier] = (1, now)
        return True, max_requests - 1
    
    async def close(self):
        """No-op for in-memory."""
        pass


class CacheManager:
    """Manages cache backend selection and initialization."""
    
    def __init__(self):
        self.cache: RedisCache | InMemoryCache | None = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize cache backend."""
        if self._initialized:
            return
        
        redis_url = getattr(settings, 'redis_url', None)
        
        if redis_url and REDIS_AVAILABLE:
            self.cache = RedisCache(redis_url)
            await self.cache.initialize()
        else:
            logger.info("Using in-memory cache (Redis not available)")
            self.cache = InMemoryCache()
            await self.cache.initialize()
        
        self._initialized = True
    
    async def get_cache(self) -> RedisCache | InMemoryCache:
        """Get cache instance, initializing if needed."""
        if not self._initialized:
            await self.initialize()
        return self.cache
    
    async def close(self):
        """Close cache connections."""
        if self.cache:
            await self.cache.close()


# Global instance
cache_manager = CacheManager()
