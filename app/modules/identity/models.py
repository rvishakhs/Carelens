import enum

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base, TenantMixin


class Role(str, enum.Enum):
    CARER = "carer"
    NURSE = "nurse"
    MANAGER = "manager"
    FAMILY = "family"
    EMERGENCY = "emergency"  # token-based, Phase 3


class User(Base, TenantMixin):
    """Mirrors the OIDC identity in Keycloak. Never stores passwords -- Keycloak owns
    credentials and MFA; this row exists so RLS/RBAC/audit have a stable local user_id."""

    __tablename__ = "users"

    oidc_subject: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


__all__ = ["User", "Role"]