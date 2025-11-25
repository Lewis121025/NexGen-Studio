"""FastAPI router for governance analytics."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..governance.models import (
    GovernanceAuditEventResponse,
    GovernanceCostSummaryCollectionResponse,
    GovernanceCostSummaryResponse,
    GovernanceEntityType,
    GovernanceUsageOverview,
)
from ..governance.service import governance_service

router = APIRouter(prefix="/governance", tags=["governance"])


@router.get(
    "/costs/{entity_type}/{entity_id}",
    response_model=GovernanceCostSummaryResponse,
)
async def get_cost_summary(entity_type: GovernanceEntityType, entity_id: str) -> GovernanceCostSummaryResponse:
    try:
        summary = await governance_service.get_cost_summary(entity_id, entity_type)
    except KeyError as exc:  # pragma: no cover - FastAPI handles translation
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return GovernanceCostSummaryResponse(summary=summary)


@router.get("/costs", response_model=GovernanceCostSummaryCollectionResponse)
async def list_costs(
    entity_type: GovernanceEntityType | None = Query(default=None),
) -> GovernanceCostSummaryCollectionResponse:
    summaries = await governance_service.list_cost_summaries(entity_type=entity_type)
    return GovernanceCostSummaryCollectionResponse(summaries=summaries)


@router.get("/audit/events", response_model=GovernanceAuditEventResponse)
async def list_audit_events(
    name: str | None = Query(default=None, description="Filter by telemetry event name"),
    limit: int = Query(default=50, ge=1, le=500),
) -> GovernanceAuditEventResponse:
    events = await governance_service.get_recent_audit_events(limit=limit, name=name)
    return GovernanceAuditEventResponse(events=events)


@router.get("/usage/overview", response_model=GovernanceUsageOverview)
async def usage_overview() -> GovernanceUsageOverview:
    return governance_service.get_usage_overview()


@router.get("/providers/metrics")
async def get_provider_metrics(provider_name: str | None = None) -> dict:
    """Get provider throttling metrics."""
    from ..provider_throttle import provider_throttle
    return await provider_throttle.get_metrics(provider_name)


@router.get("/tenants/{tenant_id}/metrics")
async def get_tenant_metrics(tenant_id: str) -> dict:
    """Get tenant sandbox policy metrics."""
    from ..tenant_policy import tenant_policy_manager
    return await tenant_policy_manager.get_tenant_metrics(tenant_id)
