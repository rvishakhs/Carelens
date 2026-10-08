from typing import Literal
from uuid import UUID

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INTELLIGENCE_", env_file=".env", extra="ignore")
    database_url: SecretStr


class MigrationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INTELLIGENCE_", env_file=".env", extra="ignore")
    migration_database_url: SecretStr



class CareLensSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CARELENS_",
        env_file=".env",
        extra="ignore",
    )

    base_url: str
    timeout_seconds: float = Field(default=10.0, gt=0, le=60)

class Settings(DatabaseSettings):
    mode: Literal["synthetic"] = "synthetic"
    provider: Literal["openai"] = "openai"
    care_home_timezone: str = "Europe/London"
    service_identity: str = "intelligence-api"
    result_ttl_seconds: int = Field(default=900, ge=1, le=86400)
    max_results: int = Field(default=100, ge=1, le=1000)


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INTELLIGENCE_",
        env_file=".env",
        extra="ignore",
    )

    broker_url: SecretStr
    handover_queue: str = "intelligence.handover"

class HandoverProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INTELLIGENCE_HANDOVER_",
        env_file=".env",
        extra="ignore",
    )

    provider: Literal["openai"] = "openai"


class OpenAIProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPENAI_",
        env_file=".env",
        extra="ignore",
    )

    api_key: SecretStr = Field(min_length=1)
    model: str = Field(default="gpt-6.1-sol", min_length=1)
    timeout_seconds: float = Field(default=25.0, gt=0, le=60)
    max_output_tokens: int = Field(default=4096, ge=256)


class WorkerIdentitySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INTELLIGENCE_", env_file=".env", extra="ignore")

    token_url: str
    client_id: str = Field(min_length=1)
    client_secret: SecretStr = Field(min_length=1)
    service_identity: str = "intelligence-api"
    minimum_token_lifetime_seconds: int = Field(default=120, ge=60, le=3600)


class DispatcherSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INTELLIGENCE_DISPATCHER_", env_file=".env", extra="ignore")

    # Explicit trusted allowlist. Never discover tenants from incoming messages.
    tenant_ids: list[UUID] = Field(min_length=1)
    poll_seconds: float = Field(default=2, gt=0, le=60)
    queued_recovery_seconds: int = Field(default=300, ge=60)


class ScheduleSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INTELLIGENCE_SCHEDULE_", env_file=".env", extra="ignore")

    enabled: bool = False
    # Bounded catch-up on restart; trusted tenant allowlist comes from DispatcherSettings.
    catch_up_shifts: int = Field(default=4, ge=1, le=14)
