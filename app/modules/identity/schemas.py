import uuid

from pydantic import BaseModel, EmailStr

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
    care_home_name: str
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


class StaffCreate(BaseModel):
    """A manager provisioning a nurse/carer -- restricted to those two roles; anything
    higher-privilege (manager, admin, headoffice, system_admin) isn't something this
    dashboard flow hands out. See identity/service.py's create_staff_member."""

    email: EmailStr
    display_name: str
    role: Role


class StaffCreated(BaseModel):
    """temporary_password is shown exactly once -- it's never stored (Keycloak forces
    a reset on first login) and never returned by any other endpoint."""

    id: uuid.UUID
    email: str
    display_name: str
    role: Role
    temporary_password: str


class StaffUpdate(BaseModel):
    """PATCH /identity/staff/{id} -- both fields optional, only the ones provided
    change. role stays restricted to the same carer/nurse set as creation (see
    identity/service.py's _STAFF_CREATABLE_ROLES): promoting someone to
    manager/admin/headoffice/system_admin isn't something this dashboard automates."""

    role: Role | None = None
    is_active: bool | None = None


class StaffCredentials(BaseModel):
    """POST /identity/staff/{id}/reset-password response -- temporary_password is
    shown exactly once, same rule as StaffCreated."""

    id: uuid.UUID
    email: str
    display_name: str
    temporary_password: str