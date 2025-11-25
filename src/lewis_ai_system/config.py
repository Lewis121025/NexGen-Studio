"""Lewis AI 系统的配置模型。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, AnyHttpUrl, BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderQuotaSettings(BaseModel):
    """托管提供商的速率限制。"""

    name: str
    rpm: int = Field(60, description="每分钟请求数限制")
    concurrent: int = Field(1, description="允许的并发请求数")


class ProviderSettings(BaseModel):
    """外部提供商配置。"""

    name: str
    base_url: AnyHttpUrl | None = None
    api_key: str | None = None
    quotas: list[ProviderQuotaSettings] = Field(default_factory=list)


class BudgetSettings(BaseModel):
    default_project_limit_usd: float = 50.0
    cost_alert_percentages: tuple[int, int] = (95, 100)


class SandboxSettings(BaseModel):
    enabled: bool = True
    execution_timeout_seconds: int = 60
    working_directory: Path = Path("/tmp/lewis")
    max_memory_mb: int = 512
    max_cpu_seconds: int = 60
    max_file_size_mb: int = 10


class TenantSandboxPolicy(BaseModel):
    """每个租户的沙箱资源限制和配额。"""
    tenant_id: str
    max_memory_mb: int = 512
    max_cpu_seconds: int = 60
    max_file_size_mb: int = 10
    execution_timeout_seconds: int = 60
    max_concurrent_executions: int = 3
    daily_execution_limit: int = 100
    enabled: bool = True


class Settings(BaseSettings):
    """全局应用程序设置。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "staging", "production"] = Field(
        default="development", alias="APP_ENV"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO", alias="LOG_LEVEL")
    api_title: str = "Lewis AI System API"
    api_version: str = "0.2.0"
    budget: BudgetSettings = BudgetSettings()
    sandbox: SandboxSettings = SandboxSettings()
    creative_preview_cost_ratio: float = 0.3
    
    # 数据库配置
    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    
    # Redis 缓存配置
    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    redis_enabled: bool = Field(default=True, alias="REDIS_ENABLED")
    
    # 对象存储 (S3 兼容)
    s3_endpoint_url: str | None = Field(default=None, alias="S3_ENDPOINT_URL")
    s3_access_key: str | None = Field(default=None, alias="S3_ACCESS_KEY")
    s3_secret_key: str | None = Field(default=None, alias="S3_SECRET_KEY")
    s3_bucket_name: str = Field(default="lewis-artifacts", alias="S3_BUCKET_NAME")
    s3_region: str = Field(default="us-east-1", alias="S3_REGION")
    
    # 向量数据库
    vector_db_type: Literal["weaviate", "qdrant", "pinecone", "none"] = Field(default="none", alias="VECTOR_DB_TYPE")
    vector_db_url: str | None = Field(default=None, alias="VECTOR_DB_URL")
    vector_db_api_key: str | None = Field(default=None, alias="VECTOR_DB_API_KEY")
    
    # 安全性
    secret_key: str = Field(default="dev-secret-key-change-in-production", alias="SECRET_KEY")
    api_key_salt: str = Field(default="dev-salt-change-in-production", alias="API_KEY_SALT")
    cors_origins: list[str] | str = Field(default_factory=lambda: ["*"], alias="CORS_ORIGINS")
    trusted_hosts: list[str] | str = Field(
        default_factory=lambda: ["*.yourdomain.com", "yourdomain.com", "localhost", "127.0.0.1"],
        alias="TRUSTED_HOSTS",
    )
    
    # 速率限制
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE")
    service_api_keys: list[str] | str = Field(default_factory=list, alias="SERVICE_API_KEYS")

    openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")
    llm_provider_mode: Literal["mock", "openrouter"] = Field(default="openrouter", alias="LLM_PROVIDER_MODE")

    runway_api_key: str | None = Field(default=None, alias="RUNWAY_API_KEY")
    pika_api_key: str | None = Field(default=None, alias="PIKA_API_KEY")
    sora_api_key: str | None = Field(default=None, alias="SORA_API_KEY")
    runware_api_key: str | None = Field(
        default=None,
        alias="RUNWARE_API_KEY",
        validation_alias=AliasChoices("RUNWARE_API_KEY", "Runware_API"),
    )
    doubao_api_key: str | None = Field(default=None, alias="DOUBAO_API_KEY")
    video_provider_default: Literal["runway", "runware", "pika", "doubao", "mock"] = Field(
        default="runway",
        alias="VIDEO_PROVIDER",
    )

    elevenlabs_api_key: str | None = Field(default=None, alias="ELEVENLABS_API_KEY")
    tavily_api_key: str | None = Field(default=None, alias="TAVILY_API_KEY")
    firecrawl_api_key: str | None = Field(default=None, alias="FIRECRAWL_API_KEY")
    zapier_nla_api_key: str | None = Field(default=None, alias="ZAPIER_NLA_API_KEY")
    e2b_api_key: str | None = Field(default=None, alias="E2B_API_KEY")
    weaviate_url: AnyHttpUrl | None = Field(default=None, alias="WEAVIATE_URL")
    weaviate_api_key: str | None = Field(default=None, alias="WEAVIATE_API_KEY")

    http_proxy: str | None = Field(default=None, alias="HTTP_PROXY")
    https_proxy: str | None = Field(default=None, alias="HTTPS_PROXY")

    llm_provider: ProviderSettings = Field(default_factory=lambda: ProviderSettings(name="openrouter"))
    video_providers: list[ProviderSettings] = Field(
        default_factory=lambda: [
            ProviderSettings(name="runway"),
            ProviderSettings(name="pika"),
        ]
    )

    def model_post_init(self, __context: dict[str, object]) -> None:
        if self.openrouter_api_key:
            self.llm_provider.api_key = self.openrouter_api_key
        for provider in self.video_providers:
            if provider.name == "runway" and self.runway_api_key:
                provider.api_key = self.runway_api_key
            if provider.name == "pika" and self.pika_api_key:
                provider.api_key = self.pika_api_key

    @model_validator(mode="after")
    def normalize_lists(self) -> "Settings":
        if isinstance(self.cors_origins, str):
            values = [item.strip() for item in self.cors_origins.split(",") if item.strip()]
            self.cors_origins = values or ["*"]
        if isinstance(self.trusted_hosts, str):
            values = [item.strip() for item in self.trusted_hosts.split(",") if item.strip()]
            self.trusted_hosts = values or ["*"]
        if isinstance(self.service_api_keys, str):
            values = [item.strip() for item in self.service_api_keys.split(",") if item.strip()]
            self.service_api_keys = values
        return self

    @model_validator(mode="after")
    def validate_production_keys(self) -> "Settings":
        """������������������ʵ�� API Keys,������ʹ�� Mock ģʽ"""
        if self.environment == "production":
            # ������ AI Provider Keys
            if self.llm_provider_mode == "mock":
                raise ValueError(
                    "Production cannot run with the mock LLM provider. "
                    "Set LLM_PROVIDER_MODE=openrouter and provide the required API keys."
                )

            missing_keys: list[str] = []
            if not self.openrouter_api_key:
                missing_keys.append("OPENROUTER_API_KEY")
            if not self.e2b_api_key:
                missing_keys.append("E2B_API_KEY")

            if missing_keys:
                raise ValueError(
                    f"Missing required production keys: {', '.join(missing_keys)}. "
                    "Populate them in the environment before starting the service."
                )

            # ������ݿ�����
            if not self.database_url:
                raise ValueError(
                    "���������������� DATABASE_URL! "
                    "������ PostgreSQL ���ݿ������ַ���"
                )

            # ��� Secret Key
            if self.secret_key == "dev-secret-key-change-in-production":
                raise ValueError(
                    "�������������޸� SECRET_KEY! "
                    "������һ����ȫ�������Կ (����ʹ�� openssl rand -hex 32)"
                )

        return self
    @property
    def httpx_proxies(self) -> str | None:
        """返回 httpx 客户端的代理 URL (首选 HTTPS)。"""
        return self.https_proxy or self.http_proxy


@lru_cache
def get_settings() -> Settings:
    """返回缓存的设置实例。"""
    return Settings()  # type: ignore[arg-type]


settings = get_settings()
