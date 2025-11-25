"""Service object powering governance APIs."""

from __future__ import annotations

from ..cost_monitor import CostMonitor, cost_monitor
from ..creative.repository import BaseCreativeProjectRepository, creative_repository
from ..general.repository import BaseGeneralSessionRepository, general_repository
from ..instrumentation import telemetry_store
from .models import (
    GovernanceAuditEvent,
    GovernanceCostSummary,
    GovernanceEntityType,
    GovernanceUsageOverview,
)


class GovernanceAnalyticsService:
    """Aggregates cost + telemetry data for the governance console."""

    def __init__(
        self,
        cost_source: CostMonitor = cost_monitor,
        creative_repo: BaseCreativeProjectRepository | None = None,
        general_repo: BaseGeneralSessionRepository | None = None,
    ) -> None:
        self.cost_monitor = cost_source
        self.creative_repo = creative_repo or creative_repository
        self.general_repo = general_repo or general_repository
        self.telemetry_store = telemetry_store

    async def get_cost_summary(
        self,
        entity_id: str,
        entity_type: GovernanceEntityType,
    ) -> GovernanceCostSummary:
        snapshot = self.cost_monitor.get_cost_summary(entity_id)
        if snapshot["snapshot_count"] == 0:
            raise KeyError(f"No cost data for {entity_type.value} {entity_id}")

        stored_type = snapshot.get("entity_type") or entity_type.value
        entity_enum = GovernanceEntityType(stored_type)
        budget_limit = snapshot.get("budget_limit") or await self._resolve_budget(entity_id, entity_enum)
        remaining_budget = (budget_limit - snapshot["current_cost"]) if budget_limit is not None else None

        return GovernanceCostSummary(
            entity_id=entity_id,
            entity_type=entity_enum,
            current_cost=snapshot["current_cost"],
            current_rate=snapshot["current_rate"],
            historical_rate=snapshot["historical_rate"],
            snapshot_count=snapshot["snapshot_count"],
            anomaly_count=snapshot["anomaly_count"],
            is_paused=snapshot["is_paused"],
            budget_limit=budget_limit,
            remaining_budget=remaining_budget,
        )

    async def list_cost_summaries(
        self,
        entity_type: GovernanceEntityType | None = None,
    ) -> list[GovernanceCostSummary]:
        summaries: list[GovernanceCostSummary] = []
        for entity_id, snapshots in self.cost_monitor.snapshots.items():
            if not snapshots:
                continue
            snapshot_type = GovernanceEntityType(snapshots[-1].entity_type)
            if entity_type and snapshot_type != entity_type:
                continue
            try:
                summary = await self.get_cost_summary(entity_id, snapshot_type)
            except KeyError:
                continue
            summaries.append(summary)
        return summaries

    async def get_recent_audit_events(self, *, limit: int = 50, name: str | None = None) -> list[GovernanceAuditEvent]:
        events = self.telemetry_store.list_events(limit=limit, name=name)
        events = list(reversed(events))
        return [
            GovernanceAuditEvent(
                name=event.name,
                timestamp=event.timestamp,
                attributes=dict(event.attributes),
            )
            for event in events
        ]

    def get_usage_overview(self) -> GovernanceUsageOverview:
        stats = self.telemetry_store.stats()
        return GovernanceUsageOverview(
            total_events=stats["total_events"],
            events_by_name=stats["events_by_name"],
            last_event_at=stats["last_event_at"],
        )

    async def _resolve_budget(self, entity_id: str, entity_type: GovernanceEntityType) -> float | None:
        try:
            if entity_type == GovernanceEntityType.PROJECT:
                project = await self.creative_repo.get(entity_id)
                return project.budget_limit_usd
            session = await self.general_repo.get(entity_id)
            return session.budget_limit_usd
        except KeyError:
            return None


governance_service = GovernanceAnalyticsService()
