from typing import Literal

from pydantic import Field, SecretStr, field_validator
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
    provider: Literal["fake"] = "fake"
    demo_token: SecretStr
    care_home_timezone: str = "Europe/London"
    service_identity: str = "intelligence-api"
    result_ttl_seconds: int = Field(default=900, ge=1, le=86400)
    max_results: int = Field(default=100, ge=1, le=1000)

    @field_validator("demo_token")
    @classmethod
    def token_is_configured(cls, value: SecretStr) -> SecretStr:
        token = value.get_secret_value()
        if len(token) < 24 or token.startswith("replace-with"):
            raise ValueError("Set a random local demo token of at least 24 characters")
        return value


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INTELLIGENCE_",
        env_file=".env",
        extra="ignore",
    )

    broker_url: SecretStr
    handover_queue: str = "intelligence.handover"
