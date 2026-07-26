import uuid

from pydantic import BaseModel

from app.modules.identity.models import Role


class CurrentUser(BaseModel):
    """What every route sees after authentication -- the shape RLS and audit are keyed
    on. Never carries the raw token."""

    id: uuid.UUID
    care_home_id: uuid.UUID
    role: Role
    email: str
    display_name: str


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: Role
    is_active: bool

    model_config = {"from_attributes": True}