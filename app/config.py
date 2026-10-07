from functools import lru_cache
from uuid import UUID

from pydantic import AwareDatetime, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.modules.identity.service_grants import IntelligenceServiceGrant


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    app_name: str = "CareLens"
    environment: str = Field(default="development")
    debug: bool = Field(default=False)

    # Temporary local testing grant; ignored outside development.
    test_floor_manager_user_id: UUID | None = None
    test_floor_manager_tenant_id: UUID | None = None
    test_floor_manager_expires_at: AwareDatetime | None = None




    # --- Key cloak ---
    # Defaulted like every other env-driven setting below (oidc_client_secret,
    # llm_api_key, ...) so tests/migrations/scripts that call get_settings() without
    # these set (they don't need Keycloak) don't crash on Settings() construction.
    #
    # These four back the *admin* client (KEYCLOAK_CLIENT_ID, e.g. "carelens-api") --
    # a confidential client with its service account granted realm-management's
    # "manage-users" role, used only by identity/adapters/keycloak_admin.py to
    # provision staff accounts. Distinct from oidc_client_id/oidc_client_secret below,
    # which are the public SPA client end users authenticate through.
    KEYCLOAK_SERVER: str = Field(default="")
    KEYCLOAK_REALM: str = Field(default="")
    KEYCLOAK_CLIENT_ID: str = Field(default="")
    keycloak_admin_client_secret: str = Field(default="")
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
    celery_broker_url: str = Field(default="redis://localhost:6379/1")
    celery_result_backend: str = Field(default="redis://localhost:6379/2")

    # --- Identity / OIDC (Keycloak) ---
    oidc_issuer: str = Field(default="http://localhost:8080/realms/CareLens")
    oidc_client_id: str = Field(default="carelens-web")
    oidc_client_secret: str = Field(default="")
    oidc_audience: str = Field(default="carelens-api")

    # Separate machine audience and explicit pilot registrations. Empty denies all.
    intelligence_service_audience: str = "carelens-intelligence-api"
    intelligence_service_grants: list[IntelligenceServiceGrant] = Field(default_factory=list)
    intelligence_staff_service_identity: str = "intelligence-api"


    # --- AI gateway ---
    llm_provider: str = Field(default="fake")  # fake | local | <real provider>
    llm_api_key: str = Field(default="")
    llm_model: str = Field(default="")

    # --- Observability ---
    sentry_dsn: str = Field(default="")
    log_level: str = Field(default="INFO")

    # --- Security ---
    cors_allowed_origins: str = Field(default="http://localhost:5174")
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
