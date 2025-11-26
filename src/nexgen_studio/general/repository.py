"""Repository implementations for General Mode sessions."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from threading import Lock
from typing import Optional

from sqlalchemy import select

from ..config import settings
from ..database import Conversation as ConversationRecord
from ..database import db_manager
from ..instrumentation import get_logger
from .models import GeneralSession, GeneralSessionCreateRequest

logger = get_logger()


class BaseGeneralSessionRepository(ABC):
    @abstractmethod
    async def create(self, payload: GeneralSessionCreateRequest) -> GeneralSession:  # pragma: no cover - interface
        raise NotImplementedError

    @abstractmethod
    async def upsert(self, session: GeneralSession) -> GeneralSession:  # pragma: no cover - interface
        raise NotImplementedError

    @abstractmethod
    async def get(self, session_id: str) -> GeneralSession:  # pragma: no cover - interface
        raise NotImplementedError

    @abstractmethod
    async def list_for_tenant(self, tenant_id: str, limit: int = 50) -> list[GeneralSession]:  # pragma: no cover - interface
        raise NotImplementedError


class InMemoryGeneralSessionRepository(BaseGeneralSessionRepository):
    def __init__(self) -> None:
        self._sessions: dict[str, GeneralSession] = {}
        self._lock = Lock()

    async def create(self, payload: GeneralSessionCreateRequest) -> GeneralSession:
        session = GeneralSession(
            id=str(uuid.uuid4()),
            tenant_id=payload.tenant_id,
            goal=payload.goal,
            max_iterations=payload.max_iterations,
            budget_limit_usd=payload.budget_limit_usd,
            auto_pause_enabled=payload.auto_pause_enabled,
        )
        return await self.upsert(session)

    async def upsert(self, session: GeneralSession) -> GeneralSession:
        with self._lock:
            self._sessions[session.id] = session
        return session

    async def get(self, session_id: str) -> GeneralSession:
        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(f"Session {session_id} not found")
        return session

    async def list_for_tenant(self, tenant_id: str, limit: int = 50) -> list[GeneralSession]:
        return [
            session for session in self._sessions.values()
            if session.tenant_id == tenant_id
        ][:limit]


class DatabaseGeneralSessionRepository(BaseGeneralSessionRepository):
    def __init__(self) -> None:
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL must be configured for DatabaseGeneralSessionRepository")

    async def create(self, payload: GeneralSessionCreateRequest) -> GeneralSession:
        session = GeneralSession(
            id=str(uuid.uuid4()),
            tenant_id=payload.tenant_id,
            goal=payload.goal,
            max_iterations=payload.max_iterations,
            budget_limit_usd=payload.budget_limit_usd,
            auto_pause_enabled=payload.auto_pause_enabled,
        )
        await self.upsert(session)
        return session

    async def upsert(self, session: GeneralSession) -> GeneralSession:
        async with db_manager.get_session() as db:
            stmt = select(ConversationRecord).where(ConversationRecord.external_id == session.id)
            record = await db.scalar(stmt)
            payload = session.model_dump(mode="json")
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if record:
                record.config_json = payload
                record.status = session.state.value
                record.iteration_count = session.iteration
                record.cost_usd = session.spent_usd
                record.max_iterations = session.max_iterations
                record.budget_limit_usd = session.budget_limit_usd
                record.last_active_at = now
            else:
                record = ConversationRecord(
                    external_id=session.id,
                    user_id=session.tenant_id,
                    mode="general",
                    status=session.state.value,
                    iteration_count=session.iteration,
                    max_iterations=session.max_iterations,
                    cost_usd=session.spent_usd,
                    budget_limit_usd=session.budget_limit_usd,
                    created_at=now,
                    last_active_at=now,
                    config_json=payload,
                )
                db.add(record)
        return session

    async def get(self, session_id: str) -> GeneralSession:
        async with db_manager.get_session() as db:
            stmt = select(ConversationRecord).where(ConversationRecord.external_id == session_id)
            record = await db.scalar(stmt)
            if not record or not record.config_json:
                raise KeyError(f"Session {session_id} not found")
            return GeneralSession.model_validate(record.config_json)

    async def list_for_tenant(self, tenant_id: str, limit: int = 50) -> list[GeneralSession]:
        async with db_manager.get_session() as db:
            stmt = (
                select(ConversationRecord)
                .where(ConversationRecord.user_id == tenant_id)
                .order_by(ConversationRecord.created_at.desc())
                .limit(limit)
            )
            results = (await db.scalars(stmt)).all()
            return [
                GeneralSession.model_validate(rec.config_json)
                for rec in results
                if rec.config_json
            ]


def _build_default_repository() -> BaseGeneralSessionRepository:
    """Build the default repository, with proper fallback logic."""
    if settings.database_url:
        try:
            # Check if database is actually available
            from ..database import db_manager
            if db_manager.engine:
                return DatabaseGeneralSessionRepository()
            else:
                logger.warning("DATABASE_URL configured but database not initialized, using in-memory repository")
        except (RuntimeError, ImportError, AttributeError) as exc:
            logger.warning("Falling back to in-memory general repository: %s", exc)
    return InMemoryGeneralSessionRepository()


class LazyGeneralSessionRepository(BaseGeneralSessionRepository):
    """
    懒加载代理 Repository，在首次使用时才初始化实际的 Repository。
    
    这解决了多 worker 模式下数据库初始化时机的问题：
    - 模块加载时不立即创建数据库连接
    - 首次调用时检查数据库状态并选择正确的实现
    - 线程安全的单例初始化
    """
    
    def __init__(self) -> None:
        self._delegate: Optional[BaseGeneralSessionRepository] = None
        self._init_lock = Lock()
    
    def _get_delegate(self) -> BaseGeneralSessionRepository:
        """获取实际的 repository 实现，懒加载并线程安全。"""
        if self._delegate is not None:
            return self._delegate
        
        with self._init_lock:
            # Double-check locking
            if self._delegate is not None:
                return self._delegate
            
            # 检查数据库是否已初始化
            if settings.database_url and db_manager.engine is not None:
                try:
                    self._delegate = DatabaseGeneralSessionRepository()
                    logger.info("General repository initialized with database backend")
                except Exception as exc:
                    logger.warning(f"Failed to initialize database repository, falling back to in-memory: {exc}")
                    self._delegate = InMemoryGeneralSessionRepository()
            else:
                self._delegate = InMemoryGeneralSessionRepository()
                if settings.database_url:
                    logger.warning("Database URL configured but engine not ready, using in-memory repository")
            
            return self._delegate
    
    def set_delegate(self, delegate: BaseGeneralSessionRepository) -> None:
        """
        显式设置底层 repository 实现。
        
        用于应用启动时在数据库初始化后切换到数据库实现。
        """
        with self._init_lock:
            old_type = type(self._delegate).__name__ if self._delegate else "None"
            self._delegate = delegate
            logger.info(f"General repository switched from {old_type} to {type(delegate).__name__}")
    
    async def create(self, payload: GeneralSessionCreateRequest) -> GeneralSession:
        return await self._get_delegate().create(payload)
    
    async def upsert(self, session: GeneralSession) -> GeneralSession:
        return await self._get_delegate().upsert(session)
    
    async def get(self, session_id: str) -> GeneralSession:
        return await self._get_delegate().get(session_id)
    
    async def list_for_tenant(self, tenant_id: str, limit: int = 50) -> list[GeneralSession]:
        return await self._get_delegate().list_for_tenant(tenant_id, limit)


# 使用懒加载代理作为全局 repository
general_repository: LazyGeneralSessionRepository = LazyGeneralSessionRepository()
