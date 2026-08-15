import uuid
from datetime import date, datetime, time

from pydantic import BaseModel

from app.modules.medications.models import MedicationEventStatus, MedicationRoute


class MedicationCreate(BaseModel):
    resident_id: uuid.UUID
    drug_name: str
    dose: str
    route: MedicationRoute
    schedule_times: list[time] = []
    is_prn: bool = False
    prn_max_per_day: int | None = None
    prn_indication: str | None = None
    prescriber: str | None = None
    start_date: date


class MedicationRead(BaseModel):
    id: uuid.UUID
    resident_id: uuid.UUID
    drug_name: str
    dose: str
    route: MedicationRoute
    schedule_times: list[time]
    is_prn: bool
    prn_max_per_day: int | None
    prn_indication: str | None
    prescriber: str | None
    start_date: date
    end_date: date | None
    stock_count: int
    stock_reorder_threshold: int
    is_active: bool

    model_config = {"from_attributes": True}


class MedicationEventCreate(BaseModel):
    status: MedicationEventStatus
    scheduled_for: datetime | None = None
    reason: str | None = None
    notes: str | None = None


class MedicationEventRead(BaseModel):
    id: uuid.UUID
    medication_id: uuid.UUID
    resident_id: uuid.UUID
    status: MedicationEventStatus
    scheduled_for: datetime | None
    administered_at: datetime | None
    reason: str | None
    administered_by: uuid.UUID | None
    witnessed_by: uuid.UUID | None
    notes: str | None

    model_config = {"from_attributes": True}


class MedicationScheduleEntry(BaseModel):
    """One resident's one scheduled (or PRN-administered) dose on the most recent day
    the care home has medication data for -- what MedicationsPage renders. `status`
    is the frontend-facing tri-state (given/due/missed), collapsed from the DB's
    6-value medication_event_status."""

    medication_event_id: uuid.UUID | None
    medication_id: uuid.UUID
    resident_id: uuid.UUID
    resident_display_name: str
    drug_name: str
    dose: str
    scheduled_for: datetime | None
    status: str  # 'given' | 'due' | 'missed'


class MedicationSchedule(BaseModel):
    day: date
    entries: list[MedicationScheduleEntry]
