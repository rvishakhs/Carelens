import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, Index, String
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.shared.database import Base


class AuditAction(str, enum.Enum):
    """Matches the DB's `audit_action` enum (migrations/versions/0001) exactly -- this
    is deliberately coarser than the domain events that feed it (see module.py); the
    specific "what happened" detail lives on the entity itself, not spelled out here."""

    VIEW = "view"
    CREATE = "create"
    UPDATE = "update"
    APPROVE = "approve"
    EXPORT = "export"
    EMERGENCY_ACCESS = "emergency_access"
    LOGIN = "login"
    LOGIN_FAILED = "login_failed"


class AuditEvent(Base):
    """Deliberately does NOT use TenantMixin -- audit rows have no updated_at or
    deleted_at because they must never change after insert. DB grants are INSERT+SELECT
    only and a trigger rejects UPDATE/DELETE (migrations/versions/0009); this model
    just mirrors that intent in the ORM layer."""

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_care_home_occurred_at", "care_home_id", "occurred_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    care_home_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(server_default=func.now())

    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(String(100), index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    justification: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    device_info: Mapped[str | None] = mapped_column(String(500), nullable=True)


__all__ = ["AuditEvent", "AuditAction"]
