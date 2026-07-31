import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base, TenantMixin


class Role(str, enum.Enum):
    CARER = "carer"
    NURSE = "nurse"
    MANAGER = "manager"
    FAMILY = "family"
    EMERGENCY = "emergency"  # token-based, Phase 3
    SYSTEM_ADMIN = "system_admin"
    ADMIN = "admin"  # migration 0013 -- per-home administrative staff
    HEADOFFICE = "headoffice"  # migration 0013 -- multi-home oversight


class User(Base, TenantMixin):
    """Mirrors the OIDC identity in Keycloak. Never stores passwords -- Keycloak owns
    credentials and MFA; this row exists so RLS/RBAC/audit have a stable local user_id."""

    __tablename__ = "users"

    oidc_subject: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(
        Enum(Role, name="user_role", values_callable=lambda enum_cls: [e.value for e in enum_cls])
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class CareHome(Base):
    __tablename__ = "care_homes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(Text)
    cqc_location_id: Mapped[str | None] = mapped_column(Text)

    address_line1: Mapped[str | None] = mapped_column(Text)
    address_line2: Mapped[str | None] = mapped_column(Text)

    city: Mapped[str | None] = mapped_column(Text)
    postcode: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)

    timezone: Mapped[str] = mapped_column(
        Text,
        default="Europe/London",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class PermissionDefinition(Base):
    """System-wide reference data (migrations/versions/0018) -- one row per
    `identity.permissions.Permission` enum value. No care_home_id, no RLS: a
    permission code means the same thing in every care home."""

    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(Text, unique=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RolePermission(Base):
    """The editable-without-a-deploy mapping app/modules/identity/permission_registry.py
    reads and caches -- this table, not ROLE_PERMISSIONS, is the runtime source of
    truth once migration 0018 has run."""

    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role", "permission_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role: Mapped[Role] = mapped_column(
        Enum(Role, name="user_role", values_callable=lambda enum_cls: [e.value for e in enum_cls])
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("permissions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())