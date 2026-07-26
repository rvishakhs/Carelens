import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.shared.database import Base


class AuditEvent(Base):
    """Deliberately does NOT use TenantMixin -- audit rows have no updated_at or
    deleted_at because they must never change after insert. DB grants are INSERT+SELECT
    only and a trigger rejects UPDATE/DELETE (see migrations/README.md); this model
    just mirrors that intent in the ORM layer."""

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_care_home_created_at", "care_home_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    care_home_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(100), index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    justification: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    event_metadata: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict)


__all__ = ["AuditEvent"]
