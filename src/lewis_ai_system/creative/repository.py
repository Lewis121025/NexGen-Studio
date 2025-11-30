"""Creative project repository implementations."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from threading import Lock
from typing import Iterable

from sqlalchemy import select

from ..database import CreativeProject as CreativeProjectRecord
from ..database import db_manager
from ..instrumentation import get_logger
from ..config import settings
from .models import CreativeProject, CreativeProjectCreateRequest

logger = get_logger()


class BaseCreativeProjectRepository(ABC):
    """Abstract repository contract for creative projects."""

    @abstractmethod
    async def create(self, payload: CreativeProjectCreateRequest) -> CreativeProject:  # pragma: no cover - interface
        raise NotImplementedError

    @abstractmethod
    async def get(self, project_id: str) -> CreativeProject:  # pragma: no cover - interface
        raise NotImplementedError

    @abstractmethod
    async def upsert(self, project: CreativeProject) -> CreativeProject:  # pragma: no cover - interface
        raise NotImplementedError

    @abstractmethod
    async def list_for_tenant(self, tenant_id: str) -> Iterable[CreativeProject]:  # pragma: no cover - interface
        raise NotImplementedError


class InMemoryCreativeProjectRepository(BaseCreativeProjectRepository):
    """Thread-safe in-memory repository used for tests and local development."""

    def __init__(self) -> None:
        self._items: dict[str, CreativeProject] = {}
        self._lock = Lock()

    async def create(self, payload: CreativeProjectCreateRequest) -> CreativeProject:
        project = CreativeProject(
            id=str(uuid.uuid4()),
            tenant_id=payload.tenant_id,
            title=payload.title,
            brief=payload.brief,
            duration_seconds=payload.duration_seconds,
            style=payload.style,
            budget_limit_usd=payload.budget_limit_usd,
            auto_pause_enabled=payload.auto_pause_enabled,
            consistency_level=payload.consistency_level,
            character_reference=payload.character_reference,
            scene_reference=payload.scene_reference,
            video_provider=payload.video_provider,
        )
        return await self.upsert(project)

    async def get(self, project_id: str) -> CreativeProject:
        project = self._items.get(project_id)
        if not project:
            raise KeyError(f"Project {project_id} not found")
        return project

    async def upsert(self, project: CreativeProject) -> CreativeProject:
        with self._lock:
            self._items[project.id] = project
        return project

    async def list_for_tenant(self, tenant_id: str) -> Iterable[CreativeProject]:
        return [p for p in self._items.values() if p.tenant_id == tenant_id]

    async def list(self, tenant_id: str = "demo", limit: int | None = None) -> Iterable[CreativeProject]:
        """List projects for a tenant with optional limit (test helper)."""
        projects = await self.list_for_tenant(tenant_id)
        if limit is not None:
            return list(projects)[:limit]
        return projects


class DatabaseCreativeProjectRepository(BaseCreativeProjectRepository):
    """SQL-backed repository that stores serialized project state in JSON."""

    def __init__(self) -> None:
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL must be configured for DatabaseCreativeProjectRepository")

    async def create(self, payload: CreativeProjectCreateRequest) -> CreativeProject:
        project = CreativeProject(
            id=str(uuid.uuid4()),
            tenant_id=payload.tenant_id,
            title=payload.title,
            brief=payload.brief,
            duration_seconds=payload.duration_seconds,
            style=payload.style,
            budget_limit_usd=payload.budget_limit_usd,
            auto_pause_enabled=payload.auto_pause_enabled,
        )
        await self.upsert(project)
        return project

    async def get(self, project_id: str) -> CreativeProject:
        record = await self._fetch_record(project_id)
        if not record:
            raise KeyError(f"Project {project_id} not found")
        return self._record_to_model(record)

    async def upsert(self, project: CreativeProject) -> CreativeProject:
        await self._persist(project)
        return project

    async def list_for_tenant(self, tenant_id: str) -> Iterable[CreativeProject]:
        async with db_manager.get_session() as db:
            stmt = select(CreativeProjectRecord).where(CreativeProjectRecord.user_id == tenant_id)
            results = (await db.scalars(stmt)).all()
            return [self._record_to_model(rec) for rec in results]

    async def _persist(self, project: CreativeProject) -> None:
        async with db_manager.get_session() as db:
            stmt = select(CreativeProjectRecord).where(CreativeProjectRecord.external_id == project.id)
            record = await db.scalar(stmt)
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if record:
                self._update_record_from_model(record, project, now)
            else:
                db.add(self._new_record_from_model(project, now))

    async def _fetch_record(self, project_id: str) -> CreativeProjectRecord | None:
        async with db_manager.get_session() as db:
            stmt = select(CreativeProjectRecord).where(CreativeProjectRecord.external_id == project_id)
            return await db.scalar(stmt)

    def _record_to_model(self, record: CreativeProjectRecord) -> CreativeProject:
        from .models import CreativeProjectState

        state_value = record.status or CreativeProjectState.BRIEF_PENDING.value
        try:
            state = CreativeProjectState(state_value)
        except Exception:
            state = CreativeProjectState.BRIEF_PENDING

        pre_pause_state = None
        if record.pre_pause_state:
            try:
                pre_pause_state = CreativeProjectState(record.pre_pause_state)
            except Exception:
                pre_pause_state = None

        return CreativeProject(
            id=record.external_id,
            tenant_id=record.user_id,
            title=record.title or "Untitled",
            brief=record.brief or "",
            summary=record.summary,
            duration_seconds=record.duration_seconds or 30,
            aspect_ratio=record.aspect_ratio or "16:9",
            video_provider=record.video_provider or "doubao",
            style=record.style or "cinematic",
            budget_limit_usd=record.budget_usd or 50.0,
            cost_usd=record.cost_usd or 0.0,
            state=state,
            pre_pause_state=pre_pause_state,
            script=record.script_text,
            storyboard=record.storyboard_json or [],
            shots=record.shots_json or [],
            render_manifest=record.render_manifest_json,
            preview_record=record.preview_json,
            validation_record=record.validation_json,
            distribution_log=record.distribution_json or [],
            pause_reason=record.pause_reason,
            paused_at=record.paused_at,
            auto_pause_enabled=record.auto_pause_enabled if record.auto_pause_enabled is not None else True,
            created_at=record.created_at or datetime.now(timezone.utc),
            updated_at=record.last_active_at or datetime.now(timezone.utc),
            error_message=record.error_message,
        )

    def _update_record_from_model(self, record: CreativeProjectRecord, project: CreativeProject, now: datetime) -> None:
        record.title = project.title
        record.brief = project.brief
        record.summary = project.summary
        record.duration_seconds = project.duration_seconds
        record.aspect_ratio = project.aspect_ratio
        record.style = project.style
        record.video_provider = project.video_provider
        record.script_text = project.script
        record.storyboard_json = [panel.model_dump(mode="json") for panel in project.storyboard]
        record.shots_json = [shot.model_dump(mode="json") for shot in project.shots]
        record.render_manifest_json = project.render_manifest.model_dump(mode="json") if project.render_manifest else None
        record.preview_json = project.preview_record.model_dump(mode="json") if project.preview_record else None
        record.validation_json = project.validation_record.model_dump(mode="json") if project.validation_record else None
        record.distribution_json = [rec.model_dump(mode="json") for rec in project.distribution_log] if project.distribution_log else None
        record.status = project.state.value
        record.cost_usd = project.cost_usd
        record.budget_usd = project.budget_limit_usd
        record.pause_reason = project.pause_reason
        record.pre_pause_state = project.pre_pause_state.value if hasattr(project.pre_pause_state, "value") else project.pre_pause_state
        record.paused_at = project.paused_at
        record.auto_pause_enabled = project.auto_pause_enabled
        record.error_message = project.error_message
        record.last_active_at = now

    def _new_record_from_model(self, project: CreativeProject, now: datetime) -> CreativeProjectRecord:
        rec = CreativeProjectRecord(
            external_id=project.id,
            user_id=project.tenant_id,
            created_at=now,
            last_active_at=now,
            cost_usd=project.cost_usd,
            budget_usd=project.budget_limit_usd,
            status=project.state.value,
        )
        self._update_record_from_model(rec, project, now)
        return rec


def _build_default_repository() -> BaseCreativeProjectRepository:
    """Build the default repository, with proper fallback logic."""
    if settings.database_url:
        try:
            # Check if database is actually available
            from ..database import db_manager
            if db_manager.engine:
                return DatabaseCreativeProjectRepository()
            else:
                logger.warning("DATABASE_URL configured but database not initialized, using in-memory repository")
        except (RuntimeError, ImportError, AttributeError) as exc:
            logger.warning("Falling back to in-memory creative repository: %s", exc)
    return InMemoryCreativeProjectRepository()


creative_repository: BaseCreativeProjectRepository = _build_default_repository()
