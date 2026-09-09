from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INTELLIGENCE_", env_file=".env", extra="ignore")
    mode: Literal["synthetic"] = "synthetic"
    provider: Literal["fake"] = "fake"
    demo_token: SecretStr
    result_ttl_seconds: int = Field(default=900, ge=1, le=86400)
    max_results: int = Field(default=100, ge=1, le=1000)

    @field_validator("demo_token")
    @classmethod
    def token_is_configured(cls, value: SecretStr) -> SecretStr:
        token = value.get_secret_value()
        if len(token) < 24 or token.startswith("replace-with"):
            raise ValueError("Set a random local demo token of at least 24 characters")
        return value
