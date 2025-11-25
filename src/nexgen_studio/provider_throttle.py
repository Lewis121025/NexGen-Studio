"""Provider throttling and rate limiting with quota management."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import settings
from .instrumentation import get_logger
from .redis_cache import cache_manager

logger = get_logger()


@dataclass
class ProviderQuota:
    """Provider quota configuration and tracking."""
    name: str
    rpm: int = 60  # Requests per minute
    concurrent: int = 1  # Concurrent requests allowed
    daily_limit: int | None = None  # Daily request limit
    retry_strategy: dict[str, Any] = field(default_factory=lambda: {
        "max_retries": 3,
        "backoff_factor": 1.5,
        "retry_on_status": [429, 500, 502, 503, 504],
    })


@dataclass
class ProviderMetrics:
    """Provider usage metrics for observability."""
    provider_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limit_hits: int = 0
    average_latency_ms: float = 0.0
    last_request_at: datetime | None = None
    daily_request_count: int = 0
    daily_reset_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0))


class ProviderThrottleManager:
    """Manages provider throttling, rate limiting, and quota enforcement."""

    def __init__(self) -> None:
        self.quotas: dict[str, ProviderQuota] = {}
        self.metrics: dict[str, ProviderMetrics] = defaultdict(lambda: ProviderMetrics(provider_name=""))
        self.active_requests: dict[str, int] = defaultdict(int)
        self.request_timestamps: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._initialize_quotas()

    def _initialize_quotas(self) -> None:
        """Initialize quotas from settings."""
        # Initialize from provider settings
        if hasattr(settings, "llm_provider") and settings.llm_provider:
            self.quotas["openrouter"] = ProviderQuota(
                name="openrouter",
                rpm=60,
                concurrent=5,
                daily_limit=10000,
            )
        
        # Initialize video provider quotas
        for provider in getattr(settings, "video_providers", []):
            if provider.name:
                self.quotas[provider.name] = ProviderQuota(
                    name=provider.name,
                    rpm=30,
                    concurrent=2,
                    daily_limit=5000,
                )
        
        # Initialize from quota settings if available
        if hasattr(settings, "llm_provider") and hasattr(settings.llm_provider, "quotas"):
            for quota_setting in settings.llm_provider.quotas:
                if quota_setting.name in self.quotas:
                    self.quotas[quota_setting.name].rpm = quota_setting.rpm
                    self.quotas[quota_setting.name].concurrent = quota_setting.concurrent

        # Initialize metrics
        for provider_name in self.quotas:
            self.metrics[provider_name] = ProviderMetrics(provider_name=provider_name)

    def get_quota(self, provider_name: str) -> ProviderQuota:
        """Get quota for a provider, creating default if not exists."""
        if provider_name not in self.quotas:
            self.quotas[provider_name] = ProviderQuota(name=provider_name)
            self.metrics[provider_name] = ProviderMetrics(provider_name=provider_name)
        return self.quotas[provider_name]

    async def check_rate_limit(self, provider_name: str) -> tuple[bool, str | None]:
        """Check if request is within rate limits. Returns (allowed, error_message)."""
        async with self._lock:
            quota = self.get_quota(provider_name)
            metrics = self.metrics[provider_name]
            
            # Reset daily count if needed
            now = datetime.now(timezone.utc)
            if now.date() > metrics.daily_reset_at.date():
                metrics.daily_request_count = 0
                metrics.daily_reset_at = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Check daily limit
            if quota.daily_limit and metrics.daily_request_count >= quota.daily_limit:
                return False, f"Daily limit ({quota.daily_limit}) exceeded for {provider_name}"
            
            # Check concurrent limit
            if self.active_requests[provider_name] >= quota.concurrent:
                return False, f"Concurrent limit ({quota.concurrent}) reached for {provider_name}"
            
            # Check RPM limit
            now_ts = time.time()
            minute_ago = now_ts - 60
            # Clean old timestamps
            self.request_timestamps[provider_name] = [
                ts for ts in self.request_timestamps[provider_name] if ts > minute_ago
            ]
            
            if len(self.request_timestamps[provider_name]) >= quota.rpm:
                return False, f"Rate limit ({quota.rpm} RPM) exceeded for {provider_name}"
            
            return True, None

    async def acquire_slot(self, provider_name: str) -> bool:
        """Acquire a request slot. Returns True if acquired, False if rate limited."""
        allowed, error_msg = await self.check_rate_limit(provider_name)
        if not allowed:
            if error_msg:
                logger.warning(f"Rate limit check failed: {error_msg}")
            metrics = self.metrics[provider_name]
            metrics.rate_limit_hits += 1
            return False
        
        async with self._lock:
            self.active_requests[provider_name] += 1
            self.request_timestamps[provider_name].append(time.time())
            metrics = self.metrics[provider_name]
            metrics.total_requests += 1
            metrics.daily_request_count += 1
            metrics.last_request_at = datetime.now(timezone.utc)
        
        return True

    async def release_slot(self, provider_name: str, success: bool = True, latency_ms: float = 0.0) -> None:
        """Release a request slot and update metrics."""
        async with self._lock:
            if self.active_requests[provider_name] > 0:
                self.active_requests[provider_name] -= 1
            
            metrics = self.metrics[provider_name]
            if success:
                metrics.successful_requests += 1
            else:
                metrics.failed_requests += 1
            
            # Update average latency
            if latency_ms > 0:
                if metrics.average_latency_ms == 0:
                    metrics.average_latency_ms = latency_ms
                else:
                    metrics.average_latency_ms = (metrics.average_latency_ms * 0.9) + (latency_ms * 0.1)

    async def get_metrics(self, provider_name: str | None = None) -> dict[str, Any]:
        """Get metrics for a provider or all providers."""
        async with self._lock:
            if provider_name:
                if provider_name not in self.metrics:
                    return {}
                metrics = self.metrics[provider_name]
                quota = self.get_quota(provider_name)
                return {
                    "provider": provider_name,
                    "quota": {
                        "rpm": quota.rpm,
                        "concurrent": quota.concurrent,
                        "daily_limit": quota.daily_limit,
                    },
                    "metrics": {
                        "total_requests": metrics.total_requests,
                        "successful_requests": metrics.successful_requests,
                        "failed_requests": metrics.failed_requests,
                        "rate_limit_hits": metrics.rate_limit_hits,
                        "average_latency_ms": metrics.average_latency_ms,
                        "daily_request_count": metrics.daily_request_count,
                        "active_requests": self.active_requests[provider_name],
                        "last_request_at": metrics.last_request_at.isoformat() if metrics.last_request_at else None,
                    },
                }
            else:
                return {
                    provider: await self.get_metrics(provider)
                    for provider in self.metrics.keys()
                }

    async def reset_metrics(self, provider_name: str | None = None) -> None:
        """Reset metrics for a provider or all providers."""
        async with self._lock:
            if provider_name:
                if provider_name in self.metrics:
                    self.metrics[provider_name] = ProviderMetrics(provider_name=provider_name)
                    self.active_requests[provider_name] = 0
                    self.request_timestamps[provider_name] = []
            else:
                for name in list(self.metrics.keys()):
                    self.metrics[name] = ProviderMetrics(provider_name=name)
                    self.active_requests[name] = 0
                    self.request_timestamps[name] = []


# Global instance
provider_throttle = ProviderThrottleManager()

