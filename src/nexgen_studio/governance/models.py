"""Pydantic models for governance-facing APIs."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GovernanceEntityType(str, Enum):
    PROJECT = "project"
    SESSION = "session"


class GovernanceCostSummary(BaseModel):
    entity_id: str
    entity_type: GovernanceEntityType
    current_cost: float
    current_rate: float
    historical_rate: float
    snapshot_count: int
    anomaly_count: int
    is_paused: bool
    budget_limit: float | None = None
    remaining_budget: float | None = None


class GovernanceCostSummaryResponse(BaseModel):
    summary: GovernanceCostSummary


class GovernanceCostSummaryCollectionResponse(BaseModel):
    summaries: list[GovernanceCostSummary] = Field(default_factory=list)


class GovernanceAuditEvent(BaseModel):
    name: str
    timestamp: datetime
    attributes: dict[str, Any]


class GovernanceAuditEventResponse(BaseModel):
    events: list[GovernanceAuditEvent]


class GovernanceUsageOverview(BaseModel):
    total_events: int
    events_by_name: dict[str, int]
    last_event_at: datetime | None = None
