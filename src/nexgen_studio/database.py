"""Database models and connection management."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, Enum as SQLEnum, Boolean, ForeignKey
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime, timezone

from .config import settings

Base = declarative_base()


# ============================================================================
# Creative Mode Models
# ============================================================================

class CreativeProject(Base):
    __tablename__ = "creative_projects"
    
    # ========== 核心标识列 ==========
    id = Column(Integer, primary_key=True)
    external_id = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(String(100), nullable=False, index=True)
    prompt_hash = Column(String(64), index=True)
    
    # ========== 核心业务字段（规范化） ==========
    title = Column(String(200), nullable=False)
    brief = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    duration_seconds = Column(Integer, nullable=False, default=5)
    aspect_ratio = Column(String(10), nullable=False, default="16:9")
    style = Column(String(50), nullable=False, default="cinematic")
    video_provider = Column(String(50), default="runway")
    script_text = Column(Text, nullable=True)
    storyboard_json = Column(JSON)
    shots_json = Column(JSON)
    render_manifest_json = Column(JSON)
    preview_json = Column(JSON)
    validation_json = Column(JSON)
    distribution_json = Column(JSON)
    error_message = Column(Text, nullable=True)
    
    # ========== 状态与暂停 ==========
    status = Column(String(50), nullable=False, default="initiated", index=True)
    pause_reason = Column(String(50), nullable=True)
    paused_at = Column(DateTime, nullable=True)
    pre_pause_state = Column(String(50), nullable=True)
    auto_resume_enabled = Column(Boolean, default=True)
    
    # ========== 预算与成本 ==========
    budget_usd = Column(Float, default=50.0, nullable=False)
    cost_usd = Column(Float, default=0.0, nullable=False)
    auto_pause_enabled = Column(Boolean, default=True)
    
    # ========== 时间戳 ==========
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    last_active_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    scripts = relationship("Script", back_populates="project", cascade="all, delete-orphan")
    storyboards = relationship("Storyboard", back_populates="project", cascade="all, delete-orphan")
    assets = relationship("ProjectAsset", back_populates="project", cascade="all, delete-orphan")


class Script(Base):
    __tablename__ = "scripts"
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("creative_projects.id"), nullable=False)
    content_text = Column(Text, nullable=False)
    version = Column(Integer, default=1)
    reviewed_by_user = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    project = relationship("CreativeProject", back_populates="scripts")


class Storyboard(Base):
    __tablename__ = "storyboards"
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("creative_projects.id"), nullable=False)
    shot_number = Column(Integer, nullable=False)
    duration_sec = Column(Integer, nullable=False)
    camera_angle = Column(String(100))
    visual_prompt = Column(Text, nullable=False)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    project = relationship("CreativeProject", back_populates="storyboards")
    shots = relationship("GeneratedShot", back_populates="storyboard", cascade="all, delete-orphan")


class ProjectAsset(Base):
    __tablename__ = "project_assets"
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("creative_projects.id"), nullable=False)
    asset_type = Column(String(50), nullable=False)
    s3_key = Column(String(500), nullable=False)
    metadata_json = Column(JSON)
    reuse_key = Column(String(64), index=True)
    origin_project_id = Column(Integer)
    reuse_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    project = relationship("CreativeProject", back_populates="assets")


class GeneratedShot(Base):
    __tablename__ = "generated_shots"
    
    id = Column(Integer, primary_key=True)
    storyboard_id = Column(Integer, ForeignKey("storyboards.id"), nullable=False)
    s3_key = Column(String(500), nullable=False)
    generation_api = Column(String(50), nullable=False)
    attempts = Column(Integer, default=1)
    retry_reason = Column(String(50), nullable=True)
    parent_shot_id = Column(Integer, ForeignKey("generated_shots.id"), nullable=True)
    quality_score = Column(Float, nullable=True)
    quality_tier = Column(String(20), default="preview")
    cost_usd = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    storyboard = relationship("Storyboard", back_populates="shots")


# ============================================================================
# General Mode Models
# ============================================================================

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True)
    external_id = Column(String(64), unique=True, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    mode = Column(String(20), default="general")
    status = Column(String(50), default="idle")
    iteration_count = Column(Integer, default=0)
    max_iterations = Column(Integer, default=10)
    cost_usd = Column(Float, default=0.0)
    budget_limit_usd = Column(Float, default=5.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_active_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    timeout_at = Column(DateTime, nullable=True)
    config_json = Column(JSON)
    
    turns = relationship("ConversationTurn", back_populates="conversation", cascade="all, delete-orphan")


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"
    
    id = Column(Integer, primary_key=True)
    conv_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant
    content_text = Column(Text, nullable=False)
    turn_number = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    conversation = relationship("Conversation", back_populates="turns")


# ============================================================================
# Shared Models
# ============================================================================

class ToolExecution(Base):
    __tablename__ = "tool_executions"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(100), nullable=False, index=True)
    session_type = Column(String(20), nullable=False)  # creative, general
    tool_name = Column(String(100), nullable=False)
    request_id = Column(String(100), unique=True, index=True)
    request_json = Column(JSON)
    response_json = Column(JSON)
    schema_valid = Column(Boolean, default=True)
    error_type = Column(String(50), nullable=True)
    duration_ms = Column(Integer)
    cost_usd = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class CostBreakdown(Base):
    __tablename__ = "cost_breakdown"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(100), nullable=False, index=True)
    session_type = Column(String(20), nullable=False)
    category = Column(String(50), nullable=False)  # llm, tts, video_gen, etc
    provider = Column(String(50), nullable=False)
    units = Column(Float, default=0.0)
    cost_usd = Column(Float, nullable=False)
    stage = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class User(Base):
    """User authentication and profile."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    api_key_hash = Column(String(128), nullable=True)  # bcrypt hash
    is_active = Column(Boolean, default=True)
    tier = Column(String(20), default="free")  # free, pro, enterprise
    budget_limit_usd = Column(Float, default=100.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login_at = Column(DateTime, nullable=True)


# ============================================================================
# Vector Database & Memory Models
# ============================================================================

class VectorEmbedding(Base):
    """Stores embeddings with metadata for semantic search."""
    __tablename__ = "vector_embeddings"
    
    id = Column(Integer, primary_key=True)
    external_id = Column(String(64), unique=True, index=True)
    collection = Column(String(100), nullable=False, index=True)
    text = Column(Text, nullable=False)
    embedding_model = Column(String(100), default="text-embedding-ada-002")
    metadata_json = Column(JSON)
    topic_id = Column(Integer, ForeignKey("user_topics.id"), nullable=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    last_accessed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class UserTopic(Base):
    """Aggregated user topics across sessions."""
    __tablename__ = "user_topics"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), nullable=False, index=True)
    topic_label = Column(String(200), nullable=False)
    summary_text = Column(Text)
    expertise_level = Column(String(20), default="beginner")  # beginner, intermediate, expert
    session_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ToolSchemaRegistry(Base):
    """Registry of tool schemas for validation."""
    __tablename__ = "tool_schema_registry"
    
    id = Column(Integer, primary_key=True)
    tool_name = Column(String(100), unique=True, nullable=False, index=True)
    schema_json = Column(JSON, nullable=False)
    version = Column(String(20), default="1.0.0")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class CostAnomalyAlert(Base):
    """Records cost anomalies and alerts."""
    __tablename__ = "cost_anomaly_alerts"
    
    id = Column(Integer, primary_key=True)
    entity_id = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(20), nullable=False)  # project, session
    alert_type = Column(String(50), nullable=False)  # rate_spike, budget_exceeded, projected_overrun
    current_rate = Column(Float, nullable=False)
    expected_rate = Column(Float, nullable=False)
    projected_total = Column(Float, nullable=False)
    budget_limit = Column(Float, nullable=False)
    message = Column(Text)
    acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class VectorIndexMaintenance(Base):
    """Logs vector index maintenance operations."""
    __tablename__ = "vector_index_maintenance_log"
    
    id = Column(Integer, primary_key=True)
    operation = Column(String(50), nullable=False)  # rebuild, quantize, cleanup
    collection = Column(String(100), nullable=False)
    records_affected = Column(Integer, default=0)
    duration_seconds = Column(Float)
    status = Column(String(20), default="success")  # success, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


# ============================================================================
# Database Connection Management
# ============================================================================

class DatabaseManager:
    """Manages async database connections."""
    
    def __init__(self):
        self.engine = None
        self.session_factory = None
    
    def initialize(self, database_url: str):
        """Initialize the database engine and session factory."""
        self.engine = create_async_engine(
            database_url,
            echo=settings.environment == "development",
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
        )
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    
    async def create_tables(self):
        """Create all tables in the database."""
        if not self.engine:
            raise RuntimeError("Database not initialized")
        
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Provide a transactional scope for database operations."""
        if not self.session_factory:
            raise RuntimeError("Database not initialized")
        
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    async def close(self):
        """Close the database engine."""
        if self.engine:
            await self.engine.dispose()


# Global instance
db_manager = DatabaseManager()


async def init_database():
    """Initialize database connection from settings."""
    if hasattr(settings, 'database_url') and settings.database_url:
        db_manager.initialize(settings.database_url)
        await db_manager.create_tables()
