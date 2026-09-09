import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app import Base, TenantMixin


class ObservationType(str, enum.Enum):
    FLUID_INTAKE = "fluid_intake"
    WEIGHT = "weight"
    VITALS = "vitals"
    MEAL = "meal"
    MOBILITY = "mobility"
    NOTE = "note"
    CONTINENCE = "continence"
    WELLBEING = "wellbeing"
    BEHAVIOUR = "behaviour"
    COMMUNICATION = "communication"
    SLEEP = "sleep"
    PAIN = "pain"
    FALL = "fall"
    INCIDENT = "incident"
    WOUND = "wound"


class Observation(Base, TenantMixin):
    """Native API submissions only (migration 0030), not copies of domain history."""

    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint("care_home_id", "idempotency_key", name="observations_home_idempotency"),
        Index("ix_observations_resident_recorded_at", "resident_id", "recorded_at"),
        Index("ix_observations_care_home_type_recorded_at", "care_home_id", "type", "recorded_at"),
    )

    resident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("residents.id"), index=True)
    type: Mapped[str] = mapped_column(
        Enum("fluid_intake", "weight", "vitals", "meal", "mobility", "note", name="observation_type"),
        index=True,
    )
    value: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    recorded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    is_implausible: Mapped[bool] = mapped_column(Boolean, default=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)


__all__ = ["Observation", "ObservationType"]
