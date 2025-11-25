import pytest

from nexgen_studio.cost_monitor import cost_monitor
from nexgen_studio.governance.models import GovernanceEntityType
from nexgen_studio.governance.service import GovernanceAnalyticsService
from nexgen_studio.instrumentation import TelemetryEvent, telemetry_store, emit_event


@pytest.mark.asyncio
async def test_governance_cost_summary_tracks_budget():
    cost_monitor.reset()
    telemetry_store.reset()
    service = GovernanceAnalyticsService()

    cost_monitor.record_snapshot("proj-governance", "project", 12.5, phase="script", budget_limit=30.0)
    summary = await service.get_cost_summary("proj-governance", GovernanceEntityType.PROJECT)

    assert summary.current_cost == pytest.approx(12.5)
    assert summary.budget_limit == pytest.approx(30.0)
    assert summary.remaining_budget == pytest.approx(17.5)


@pytest.mark.asyncio
async def test_governance_audit_events_and_usage():
    telemetry_store.reset()
    cost_monitor.reset()
    service = GovernanceAnalyticsService()

    emit_event(TelemetryEvent(name="tool_start", attributes={"tool": "python"}))
    emit_event(TelemetryEvent(name="tool_complete", attributes={"tool": "python"}))

    events = await service.get_recent_audit_events(limit=2)
    assert len(events) == 2
    assert events[0].name in {"tool_start", "tool_complete"}

    overview = service.get_usage_overview()
    assert overview.total_events >= 2
    assert "tool_start" in overview.events_by_name
