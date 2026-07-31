import uuid

from pydantic import BaseModel

from app.modules.identity.models import Role


class CurrentUser(BaseModel):
    """What every route sees after authentication -- the shape RLS and audit are keyed
    on. Never carries the raw token.

    `floor_ids` is the user's full *authorisation* (migrations/versions/0013's
    user_floor_links), resolved once at login -- not a per-session subset. Every
    rls_session() call for a floor-scoped table should pass this straight through;
    see app/shared/database.py's docstring for what happens if it's omitted."""

    id: uuid.UUID
    care_home_id: uuid.UUID
    role: Role
    email: str
    display_name: str
    floor_ids: list[uuid.UUID] = []


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: Role
    is_active: bool

    model_config = {"from_attributes": True}