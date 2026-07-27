import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, Text, Uuid, func
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