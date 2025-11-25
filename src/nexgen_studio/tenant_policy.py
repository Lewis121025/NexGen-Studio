"""Tenant-specific sandbox policies and quota management."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .config import TenantSandboxPolicy
from .instrumentation import get_logger
from .redis_cache import cache_manager

logger = get_logger()


class TenantPolicyManager:
    """Manages tenant-specific sandbox policies and quotas."""

    def __init__(self) -> None:
        self.policies: dict[str, TenantSandboxPolicy] = {}
        self.execution_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.active_executions: dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()
        self._default_policy = TenantSandboxPolicy(tenant_id="default")

    def get_policy(self, tenant_id: str) -> TenantSandboxPolicy:
        """Get policy for a tenant, returning default if not configured."""
        if tenant_id in self.policies:
            return self.policies[tenant_id]
        return self._default_policy

    def set_policy(self, policy: TenantSandboxPolicy) -> None:
        """Set or update a tenant policy."""
        self.policies[policy.tenant_id] = policy
        logger.info(f"Updated policy for tenant {policy.tenant_id}")

    async def check_quota(self, tenant_id: str) -> tuple[bool, str | None]:
        """Check if tenant has quota available. Returns (allowed, error_message)."""
        async with self._lock:
            policy = self.get_policy(tenant_id)
            
            if not policy.enabled:
                return False, f"Sandbox disabled for tenant {tenant_id}"
            
            # Check concurrent executions
            if self.active_executions[tenant_id] >= policy.max_concurrent_executions:
                return False, f"Concurrent execution limit ({policy.max_concurrent_executions}) reached"
            
            # Check daily limit
            today = datetime.now(timezone.utc).date().isoformat()
            daily_key = f"{tenant_id}:{today}"
            if self.execution_counts[tenant_id][daily_key] >= policy.daily_execution_limit:
                return False, f"Daily execution limit ({policy.daily_execution_limit}) exceeded"
            
            return True, None

    async def acquire_execution_slot(self, tenant_id: str) -> bool:
        """Acquire an execution slot for a tenant."""
        allowed, error_msg = await self.check_quota(tenant_id)
        if not allowed:
            if error_msg:
                logger.warning(f"Quota check failed for tenant {tenant_id}: {error_msg}")
            return False
        
        async with self._lock:
            self.active_executions[tenant_id] += 1
            today = datetime.now(timezone.utc).date().isoformat()
            daily_key = f"{tenant_id}:{today}"
            self.execution_counts[tenant_id][daily_key] += 1
        
        return True

    async def release_execution_slot(self, tenant_id: str) -> None:
        """Release an execution slot for a tenant."""
        async with self._lock:
            if self.active_executions[tenant_id] > 0:
                self.active_executions[tenant_id] -= 1

    def get_sandbox_config(self, tenant_id: str) -> dict[str, Any]:
        """Get sandbox configuration for a tenant."""
        policy = self.get_policy(tenant_id)
        return {
            "max_memory_mb": policy.max_memory_mb,
            "max_cpu_seconds": policy.max_cpu_seconds,
            "max_file_size_mb": policy.max_file_size_mb,
            "execution_timeout_seconds": policy.execution_timeout_seconds,
        }

    async def get_tenant_metrics(self, tenant_id: str) -> dict[str, Any]:
        """Get metrics for a tenant."""
        async with self._lock:
            policy = self.get_policy(tenant_id)
            today = datetime.now(timezone.utc).date().isoformat()
            daily_key = f"{tenant_id}:{today}"
            
            return {
                "tenant_id": tenant_id,
                "policy": {
                    "max_memory_mb": policy.max_memory_mb,
                    "max_cpu_seconds": policy.max_cpu_seconds,
                    "max_file_size_mb": policy.max_file_size_mb,
                    "execution_timeout_seconds": policy.execution_timeout_seconds,
                    "max_concurrent_executions": policy.max_concurrent_executions,
                    "daily_execution_limit": policy.daily_execution_limit,
                    "enabled": policy.enabled,
                },
                "current_usage": {
                    "active_executions": self.active_executions[tenant_id],
                    "daily_executions": self.execution_counts[tenant_id].get(daily_key, 0),
                },
            }


# Global instance
tenant_policy_manager = TenantPolicyManager()

