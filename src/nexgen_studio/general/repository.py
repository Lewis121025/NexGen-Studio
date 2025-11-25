"""Repository implementations for General Mode sessions."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from threading import Lock

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


general_repository: BaseGeneralSessionRepository = _build_default_repository()
