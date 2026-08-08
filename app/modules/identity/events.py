import uuid

from app.shared.events import DomainEvent


class UserLoggedIn(DomainEvent):
    user_id: uuid.UUID
    role: str


class StaffMemberCreated(DomainEvent):
    user_id: uuid.UUID
    role: str


class StaffMemberUpdated(DomainEvent):
    user_id: uuid.UUID
    role: str
    is_active: bool


class StaffPasswordReset(DomainEvent):
    user_id: uuid.UUID


class MfaChallengeFailed(DomainEvent):
    """Published by Keycloak's login flow via a webhook/event listener in Phase 1's
    thin integration -- audit subscribes so repeated MFA failures are visible to
    managers without needing Keycloak's own admin console."""

    user_id: uuid.UUID | None
    reason: str