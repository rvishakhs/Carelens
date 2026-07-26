import uuid
from datetime import datetime, time

from pydantic import BaseModel

from app.modules.medications.models import MedicationEventStatus


class MedicationCreate(BaseModel):
    resident_id: uuid.UUID
    name: str
    dose: str
    route: str
    scheduled_times: list[time]


class MedicationRead(BaseModel):
    id: uuid.UUID
    resident_id: uuid.UUID
    name: str
    dose: str
    route: str
    scheduled_times: list[time]
    stock_remaining: int

    model_config = {"from_attributes": True}


class MedicationEventCreate(BaseModel):
    status: MedicationEventStatus
    scheduled_at: datetime
    notes: str | None = None


class MedicationEventRead(BaseModel):
    id: uuid.UUID
    medication_id: uuid.UUID
    resident_id: uuid.UUID
    status: MedicationEventStatus
    scheduled_at: datetime
    recorded_at: datetime
    recorded_by: uuid.UUID
    notes: str | None

    model_config = {"from_attributes": True}
