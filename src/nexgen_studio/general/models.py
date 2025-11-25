"""General mode data models and state machine."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class GuardrailTriggered(RuntimeError):
    """Raised when a guardrail stops general mode execution."""

    def __init__(self, reason: str, detail: str | None = None) -> None:
        self.reason = reason
        message = detail or reason
        super().__init__(message)


class GeneralSessionState(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class ToolCallRecord(BaseModel):
    step: int
    tool: str
    arguments: dict
    output: dict | str
    cost_usd: float
    decision_path: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UploadedFileMeta(BaseModel):
    name: str
    content_type: str | None = None
    size_bytes: int
    local_path: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GeneralSession(BaseModel):
    id: str
    tenant_id: str
    goal: str
    state: GeneralSessionState = GeneralSessionState.ACTIVE
    max_iterations: int = 8
    iteration: int = 0
    budget_limit_usd: float = 5.0
    spent_usd: float = 0.0
    auto_pause_enabled: bool = True
    pause_reason: str | None = None
    summary: str | None = None
    messages: list[str] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    uploads: list[UploadedFileMeta] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def mark_state(self, state: GeneralSessionState) -> None:
        self.state = state
        self.updated_at = datetime.now(timezone.utc)


class GeneralSessionCreateRequest(BaseModel):
    tenant_id: str = "demo"
    goal: str
    max_iterations: int = 6
    budget_limit_usd: float = 5.0
    auto_pause_enabled: bool = True


class GeneralSessionResponse(BaseModel):
    session: GeneralSession


class GeneralSessionListResponse(BaseModel):
    sessions: list[GeneralSession]
