import uuid
from datetime import date

from pydantic import BaseModel

from app.modules.residents.models import ResidentStatus


class ResidentCreate(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    room_number: str
    floor_id: uuid.UUID | None = None


class ResidentRead(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    date_of_birth: date
    room_number: str | None
    floor_id: uuid.UUID | None
    status: ResidentStatus

    model_config = {"from_attributes": True}


class ResidentSummary(BaseModel):
    """Minimal shape exposed cross-module via ResidentReader -- callers outside
    residents/ never see the full record, just enough to render a name + room."""

    id: uuid.UUID
    display_name: str
    room_number: str | None
    status: ResidentStatus

    model_config = {"from_attributes": True}
