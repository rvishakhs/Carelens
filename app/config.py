from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    app_name: str = "CareLens"
    environment: str = Field(default="development")
    debug: bool = Field(default=False)



    # --- Key cloak ---
    KEYCLOAK_SERVER: str
    KEYCLOAK_REALM: str
    KEYCLOAK_CLIENT_ID: str
    # --- Modules (comma-separated; controls what main.py registers) ---
    enabled_modules: str = Field(
        default="identity,residents,floors,observations,care_recording,audit,ai_gateway,summaries,ai_insights,handover"
    )

    # --- Feature flags (for incomplete features within an enabled module; whole-module
    # enable/disable goes through enabled_modules instead, e.g. "medications") ---
    feature_voice_notes: bool = Field(default=False)

    # --- Database ---
    database_url: str = Field(
        validation_alias="DATABASE_URL"
    )

    db_pool_size: int = Field(default=10)

    # --- Redis / jobs ---
    redis_url: str = Field(default="redis://localhost:6379/0")

    # --- Identity / OIDC (Keycloak) ---
    oidc_issuer: str = Field(default="http://localhost:8080/realms/carelens")
    oidc_client_id: str = Field(default="carelens-app")
    oidc_client_secret: str = Field(default="")
    oidc_audience: str = Field(default="carelens-app")

    # --- AI gateway ---
    llm_provider: str = Field(default="fake")  # fake | local | <real provider>
    llm_api_key: str = Field(default="")
    llm_model: str = Field(default="")

    # --- Observability ---
    sentry_dsn: str = Field(default="")
    log_level: str = Field(default="INFO")

    # --- Security ---
    cors_allowed_origins: str = Field(default="http://localhost:5173")
    secret_key: str = Field(default="change-me-in-env")

    @property
    def enabled_modules_list(self) -> list[str]:
        return [m.strip() for m in self.enabled_modules.split(",") if m.strip()]

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()