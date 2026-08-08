import uuid

from app.modules.identity.events import StaffMemberCreated, StaffMemberUpdated, StaffPasswordReset, UserLoggedIn
from app.modules.identity.models import Role
from app.modules.identity.ports import IdentityProviderAdmin
from app.modules.identity.repository import UserRepository
from app.modules.identity.schemas import CurrentUser, StaffCreate, StaffCreated, StaffCredentials, StaffUpdate, UserRead
from app.shared.events import EventBus
from app.shared.exceptions import NotFoundError, ValidationError
from app.shared.security import generate_opaque_token

_STAFF_CREATABLE_ROLES = frozenset({Role.CARER, Role.NURSE})


class IdentityService:
    def __init__(self, repository: UserRepository, identity_provider_admin: IdentityProviderAdmin, event_bus: EventBus):
        self._repository = repository
        self._identity_provider_admin = identity_provider_admin
        self._event_bus = event_bus

    async def record_login(self, user: CurrentUser) -> None:
        await self._event_bus.publish(
            UserLoggedIn(care_home_id=user.care_home_id, actor_user_id=user.id, user_id=user.id, role=user.role.value)
        )

    async def create_staff_member(
        self, care_home_id: uuid.UUID, actor_user_id: uuid.UUID, data: StaffCreate
    ) -> StaffCreated:
        """Provisions a nurse/carer end-to-end: creates their Keycloak account first
        (the source of truth for the oidc_subject the local row is keyed on), then
        mirrors it locally scoped to the manager's own care home. If the local insert
        fails, the Keycloak account is left orphaned rather than half-provisioned
        locally with no way to log in -- acceptable for now (single care home,
        manager can retry/clean up by hand); worth a compensating action once this
        flow has real usage."""
        if data.role not in _STAFF_CREATABLE_ROLES:
            allowed = sorted(r.value for r in _STAFF_CREATABLE_ROLES)
            raise ValidationError(f"manager-created staff must be one of {allowed}")

        temporary_password = generate_opaque_token(9)
        oidc_subject = await self._identity_provider_admin.create_user(
            email=data.email,
            display_name=data.display_name,
            role=data.role.value,
            temporary_password=temporary_password,
        )
        user = await self._repository.create_provisioned(
            care_home_id=care_home_id,
            oidc_subject=oidc_subject,
            email=data.email,
            display_name=data.display_name,
            role=data.role,
        )
        await self._event_bus.publish(
            StaffMemberCreated(
                care_home_id=care_home_id, actor_user_id=actor_user_id, user_id=user.id, role=user.role.value
            )
        )
        return StaffCreated(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            temporary_password=temporary_password,
        )

    async def update_staff_member(
        self, care_home_id: uuid.UUID, actor_user_id: uuid.UUID, user_id: uuid.UUID, data: StaffUpdate
    ) -> UserRead:
        """Edits role and/or active status. `get_by_id` runs inside the caller's own
        rls_session (identity/router.py's get_user_repository), so it's already
        tenant-scoped -- a user_id belonging to a different care home 404s here the
        same as one that doesn't exist, RLS just makes it invisible rather than this
        code having to check care_home_id by hand."""
        if user_id == actor_user_id:
            raise ValidationError("cannot change your own role or active status from this screen")

        user = await self._repository.get_by_id(user_id)
        if user is None:
            raise NotFoundError(f"staff member {user_id} not found")

        if data.role is not None:
            if data.role not in _STAFF_CREATABLE_ROLES:
                allowed = sorted(r.value for r in _STAFF_CREATABLE_ROLES)
                raise ValidationError(f"role must be one of {allowed}")
            user.role = data.role

        if data.is_active is not None and data.is_active != user.is_active:
            # Keycloak-side disable first: if it fails, the local row (and the audit
            # trail below) never reflects a state Keycloak doesn't also enforce.
            await self._identity_provider_admin.set_enabled(user.oidc_subject, data.is_active)
            user.is_active = data.is_active

        await self._repository.save(user)
        await self._event_bus.publish(
            StaffMemberUpdated(
                care_home_id=care_home_id,
                actor_user_id=actor_user_id,
                user_id=user.id,
                role=user.role.value,
                is_active=user.is_active,
            )
        )
        return UserRead.model_validate(user)

    async def reset_staff_password(
        self, care_home_id: uuid.UUID, actor_user_id: uuid.UUID, user_id: uuid.UUID
    ) -> StaffCredentials:
        user = await self._repository.get_by_id(user_id)
        if user is None:
            raise NotFoundError(f"staff member {user_id} not found")

        temporary_password = generate_opaque_token(9)
        await self._identity_provider_admin.set_temporary_password(user.oidc_subject, temporary_password)

        await self._event_bus.publish(
            StaffPasswordReset(care_home_id=care_home_id, actor_user_id=actor_user_id, user_id=user.id)
        )
        return StaffCredentials(
            id=user.id, email=user.email, display_name=user.display_name, temporary_password=temporary_password
        )