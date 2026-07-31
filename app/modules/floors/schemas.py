import uuid

from pydantic import BaseModel

from app.modules.floors.models import FloorType


class FloorCreate(BaseModel):
    name: str
    floor_type: FloorType = FloorType.OTHER
    description: str | None = None


class FloorRead(BaseModel):
    id: uuid.UUID
    name: str
    floor_type: FloorType
    description: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class UserFloorLinkCreate(BaseModel):
    user_id: uuid.UUID
    floor_id: uuid.UUID
