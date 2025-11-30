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
    # 一致性控制字段
    consistency_prompt: str | None = None   # 增强的一致性提示词
    reference_image_url: str | None = None  # 使用的参考图片
    character_features: dict[str, Any] | None = None  # 角色特征提取
    consistency_score: float | None = None  # 一致性评分


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
    # 一致性控制字段
    reference_image_url: str | None = None  # 使用的参考图片
    consistency_seed: int | None = None    # 一致性种子
    character_prompt: str | None = None     # 角色一致性提示
    consistency_score: float | None = None  # 视频一致性评分


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
    video_provider: str = "doubao"  # 固定为豆包
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
    # 一致性控制字段
    consistency_level: Literal["low", "medium", "high"] = "medium"
    character_reference: str | None = None  # 角色参考描述
    scene_reference: str | None = None      # 场景参考描述
    consistency_seed: int | None = None     # 随机种子
    reference_images: list[str] = Field(default_factory=list)  # 参考图片URLs
    overall_consistency_score: float | None = None  # 整体一致性评分

    # 高级一致性控制选项
    enable_auto_retry: bool = True          # 启用自动重试
    max_retry_attempts: int = 2             # 最大重试次数
    consistency_threshold: float = 0.7      # 一致性阈值
    character_priority: float = 0.4         # 角色一致性权重
    scene_priority: float = 0.3             # 场景一致性权重
    style_priority: float = 0.2             # 风格一致性权重
    visual_priority: float = 0.1            # 视觉相似性权重
    custom_consistency_rules: dict[str, Any] = Field(default_factory=dict)  # 自定义一致性规则
    consistency_model_version: str = "gemini-2.5-flash-lite"  # 使用的AI模型版本
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def mark_state(self, new_state: CreativeProjectState) -> None:
        self.state = new_state
        self.updated_at = datetime.now(timezone.utc)

    @property
    def panels(self) -> list[StoryboardPanel]:
        """Alias for storyboard panels (test convenience)."""
        return self.storyboard

    @property
    def status(self) -> str:
        """String alias for current state."""
        if self.state == CreativeProjectState.SCRIPT_REVIEW:
            return CreativeProjectState.SCRIPT_PENDING.value
        return self.state.value


class CreativeProjectCreateRequest(BaseModel):
    tenant_id: str = "demo"
    title: str
    brief: str
    duration_seconds: int = 30
    style: str = "cinematic"
    video_provider: str = "runway"  # 添加视频提供商选择，默认为runway
    budget_limit_usd: float = 50.0
    auto_pause_enabled: bool = True
    # 一致性控制选项
    consistency_level: Literal["low", "medium", "high"] = "medium"
    character_reference: str | None = None
    scene_reference: str | None = None


class CreativeProjectResponse(BaseModel):
    project: CreativeProject


class CreativeProjectListResponse(BaseModel):
    projects: list[CreativeProject]
