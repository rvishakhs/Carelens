import enum
import uuid
from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, SmallInteger, Text, Time
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.shared.database import Base, TenantMixin


class MedicationRoute(str, enum.Enum):
    ORAL = "oral"
    TOPICAL = "topical"
    SUBCUTANEOUS = "subcutaneous"
    INTRAMUSCULAR = "intramuscular"
    INHALED = "inhaled"
    PATCH = "patch"
    PEG = "peg"
    EYE_DROP = "eye_drop"
    EAR_DROP = "ear_drop"
    SUPPOSITORY = "suppository"
    OTHER = "other"


class MedicationEventStatus(str, enum.Enum):
    ADMINISTERED = "administered"
    REFUSED = "refused"
    OMITTED = "omitted"
    NOT_AVAILABLE = "not_available"
    SELF_ADMINISTERED = "self_administered"
    VOMITED_AFTER = "vomited_after"


class Medication(Base, TenantMixin):
    __tablename__ = "medications"

    resident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("residents.id"), index=True)
    drug_name: Mapped[str] = mapped_column(Text)
    dose: Mapped[str] = mapped_column(Text)
    route: Mapped[MedicationRoute] = mapped_column(
        Enum(MedicationRoute, name="medication_route", values_callable=lambda enum_cls: [e.value for e in enum_cls])
    )
    schedule_times: Mapped[list[time]] = mapped_column(ARRAY(Time), default=list)
    is_prn: Mapped[bool] = mapped_column(Boolean, default=False)
    prn_max_per_day: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    prn_indication: Mapped[str | None] = mapped_column(Text, nullable=True)
    prescriber: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    stock_count: Mapped[int] = mapped_column(Integer, default=0)
    stock_reorder_threshold: Mapped[int] = mapped_column(Integer, default=7)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MedicationEvent(Base):
    """No TenantMixin here -- unlike every mixin-using table, medication_events
    (migration 0007) has no `updated_at` column (append-mostly: a recorded dose isn't
    edited, just occasionally annotated). Mirrors audit/models.py's AuditEvent, the
    other table in this position."""

    __tablename__ = "medication_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    care_home_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    medication_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medications.id"), index=True)
    resident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("residents.id"), index=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    administered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[MedicationEventStatus] = mapped_column(
        Enum(MedicationEventStatus, name="medication_event_status", values_callable=lambda enum_cls: [e.value for e in enum_cls])
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    administered_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    witnessed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = ["Medication", "MedicationEvent", "MedicationEventStatus", "MedicationRoute"]
