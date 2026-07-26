import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base, TenantMixin


class ObservationType(str, enum.Enum):
    FLUID_INTAKE = "fluid_intake"
    WEIGHT = "weight"
    VITALS = "vitals"
    MEAL = "meal"
    MOBILITY = "mobility"
    NOTE = "note"


class Observation(Base, TenantMixin):
    """value is JSONB -- payload shape depends on `type` (see schemas.py validators
    for per-type plausibility bounds). A numeric projection for common metrics is
    added as a generated column in the Alembic migration, not here, so it can be
    indexed without an ORM round-trip."""

    __tablename__ = "observations"
    __table_args__ = (
        Index("ix_observations_resident_recorded_at", "resident_id", "recorded_at"),
        Index("ix_observations_care_home_type_recorded_at", "care_home_id", "type", "recorded_at"),
    )

    resident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("residents.id"), index=True)
    type: Mapped[ObservationType] = mapped_column(Enum(ObservationType, name="observation_type"), index=True)
    value: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    recorded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    is_implausible: Mapped[bool] = mapped_column(Boolean, default=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)


__all__ = ["Observation", "ObservationType"]
