import enum
import uuid
from datetime import datetime, time

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Time
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base, TenantMixin


class MedicationEventStatus(str, enum.Enum):
    ADMINISTERED = "administered"
    REFUSED = "refused"
    MISSED = "missed"


class Medication(Base, TenantMixin):
    __tablename__ = "medications"

    resident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("residents.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    dose: Mapped[str] = mapped_column(String(100))
    route: Mapped[str] = mapped_column(String(50))
    scheduled_times: Mapped[list[time]] = mapped_column(ARRAY(Time))
    stock_remaining: Mapped[int] = mapped_column(Integer, default=0)


class MedicationEvent(Base, TenantMixin):
    __tablename__ = "medication_events"

    medication_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medications.id"), index=True)
    resident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("residents.id"), index=True)
    status: Mapped[MedicationEventStatus] = mapped_column(Enum(MedicationEventStatus, name="medication_event_status"))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)


__all__ = ["Medication", "MedicationEvent", "MedicationEventStatus"]
