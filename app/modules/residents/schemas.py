import uuid
from datetime import date

from pydantic import BaseModel

from app.modules.residents.models import ResidentStatus


class ResidentCreate(BaseModel):
    """floor_id is required, not just nullable-with-a-default: migration 0013's
    floor-scoped SELECT policy has no `floor_id IS NULL` exception (only INSERT/UPDATE
    do), so a resident created without one can never be read back -- including by the
    very request that creates it, since the ORM's INSERT...RETURNING needs the new row
    to pass the SELECT policy too. NULL is only for pre-existing rows a migration
    backfill hasn't caught up to yet, never for anything the app creates going
    forward."""

    first_name: str
    last_name: str
    date_of_birth: date
    room_number: str
    floor_id: uuid.UUID


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
