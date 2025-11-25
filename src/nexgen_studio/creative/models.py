"""Creative mode data models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class CreativeProjectState(str, Enum):
    BRIEF_PENDING = "brief_pending"
    SCRIPT_PENDING = "script_pending"
    SCRIPT_REVIEW = "script_review"
    STORYBOARD_PENDING = "storyboard_pending"
    STORYBOARD_READY = "storyboard_ready"
    RENDER_PENDING = "render_pending"
    PREVIEW_PENDING = "preview_pending"
    PREVIEW_READY = "preview_ready"
    VALIDATION_PENDING = "validation_pending"
    DISTRIBUTION_PENDING = "distribution_pending"
    COMPLETED = "completed"
    PAUSED = "paused"
    FAILED = "failed"


class StoryboardPanel(BaseModel):
    scene_number: int
    description: str
    duration_seconds: int
    camera_notes: str | None = None
    visual_reference_path: str | None = None
    quality_score: float | None = None
    status: Literal["draft", "approved", "needs_revision"] = "draft"


class GeneratedShotAsset(BaseModel):
    scene_number: int
    prompt: str
    provider: str
    job_id: str | None = None
    video_url: str | None = None
    asset_path: str | None = None
    status: Literal["processing", "completed", "failed"] = "processing"
    quality: Literal["preview", "final"] = "preview"
    metadata: dict[str, Any] | None = None
    error_message: str | None = None


class RenderManifest(BaseModel):
    master_path: str
    duration_seconds: int
    shot_count: int
    sources: list[str]
    status: Literal["assembling", "ready"] = "assembling"


class PreviewRecord(BaseModel):
    """Preview generation and review record."""
    preview_url: str | None = None
    preview_path: str | None = None
    quality_score: float | None = None
    qc_status: Literal["pending", "approved", "needs_revision", "rejected"] = "pending"
    qc_notes: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ValidationRecord(BaseModel):
    """Final validation record before distribution."""
    validation_status: Literal["pending", "approved", "rejected"] = "pending"
    validator: str | None = None
    validation_notes: str | None = None
    quality_checks: list[dict[str, Any]] = Field(default_factory=list)
    validated_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DistributionRecord(BaseModel):
    channel: Literal["s3", "webhook", "manual"]
    status: Literal["pending", "completed", "failed"]
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CreativeProject(BaseModel):
    id: str
    tenant_id: str
    title: str
    brief: str
    summary: str | None = None
    duration_seconds: int = 30
    style: str = "cinematic"
    aspect_ratio: str = "16:9"
    video_provider: str = "runway"
    budget_limit_usd: float = 50.0
    cost_usd: float = 0.0
    state: CreativeProjectState = CreativeProjectState.BRIEF_PENDING
    pre_pause_state: CreativeProjectState | None = None
    script: str | None = None
    storyboard: list[StoryboardPanel] = Field(default_factory=list)
    shots: list[GeneratedShotAsset] = Field(default_factory=list)
    render_manifest: RenderManifest | None = None
    preview_record: PreviewRecord | None = None
    validation_record: ValidationRecord | None = None
    distribution_log: list[DistributionRecord] = Field(default_factory=list)
    error_message: str | None = None
    pause_reason: str | None = None
    paused_at: datetime | None = None
    auto_pause_enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def mark_state(self, new_state: CreativeProjectState) -> None:
        self.state = new_state
        self.updated_at = datetime.now(timezone.utc)


class CreativeProjectCreateRequest(BaseModel):
    tenant_id: str = "demo"
    title: str
    brief: str
    duration_seconds: int = 30
    style: str = "cinematic"
    budget_limit_usd: float = 50.0
    auto_pause_enabled: bool = True


class CreativeProjectResponse(BaseModel):
    project: CreativeProject


class CreativeProjectListResponse(BaseModel):
    projects: list[CreativeProject]
