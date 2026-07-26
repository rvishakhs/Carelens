import uuid
from datetime import date

from pydantic import BaseModel

from app.modules.residents.models import ResidentStatus


class ResidentCreate(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    room: str
    data_processing_consent: bool = True
    photo_consent: bool = False


class ResidentRead(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    date_of_birth: date
    room: str
    status: ResidentStatus
    data_processing_consent: bool
    photo_consent: bool

    model_config = {"from_attributes": True}


class ResidentSummary(BaseModel):
    """Minimal shape exposed cross-module via ResidentReader -- callers outside
    residents/ never see the full record, just enough to render a name + room."""

    id: uuid.UUID
    display_name: str
    room: str
    status: ResidentStatus

    model_config = {"from_attributes": True}