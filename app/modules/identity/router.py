import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request

from app.modules.identity.dependencies import get_current_user
from app.modules.identity.permissions import Permission, require
from app.modules.identity.repository import UserRepository
from app.modules.identity.schemas import CurrentUser, StaffCreate, StaffCreated, StaffCredentials, StaffUpdate, UserRead
from app.modules.identity.service import IdentityService
from app.shared.database import rls_session

router = APIRouter(prefix="/identity", tags=["identity"])


async def get_user_repository(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncIterator[UserRepository]:
    async with rls_session(current_user.care_home_id, current_user.id) as session:
        yield UserRepository(session)


def get_identity_service(
    request: Request, repository: UserRepository = Depends(get_user_repository)
) -> IdentityService:
    container = request.app.state.container
    return IdentityService(repository, container.identity_provider_admin, container.event_bus)


@router.get("/me", response_model=CurrentUser)
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),
    service: IdentityService = Depends(get_identity_service),
) -> CurrentUser:
    await service.record_login(current_user)
    return current_user


@router.post("/staff", response_model=StaffCreated, status_code=201)
async def create_staff_member(
    payload: StaffCreate,
    current_user: CurrentUser = Depends(require(Permission.MANAGE_USERS)),
    service: IdentityService = Depends(get_identity_service),
) -> StaffCreated:
    """Provisions a nurse/carer: creates their Keycloak account and this care home's
    local mirror row together. temporary_password is only ever returned here -- show
    it to the manager once, it can't be recovered afterwards."""
    return await service.create_staff_member(current_user.care_home_id, current_user.id, payload)


@router.get("/staff", response_model=list[UserRead])
async def list_staff(
    _: CurrentUser = Depends(require(Permission.MANAGE_USERS)),
    repository: UserRepository = Depends(get_user_repository),
) -> list[UserRead]:
    """Includes deactivated staff (list_all(), not list_active()) so a manager can see
    -- and reactivate -- accounts they've turned off, not just active ones."""
    users = await repository.list_all()
    return [UserRead.model_validate(u) for u in users]


@router.patch("/staff/{user_id}", response_model=UserRead)
async def update_staff_member(
    user_id: uuid.UUID,
    payload: StaffUpdate,
    current_user: CurrentUser = Depends(require(Permission.MANAGE_USERS)),
    service: IdentityService = Depends(get_identity_service),
) -> UserRead:
    """Edits role and/or active status. role stays restricted to carer/nurse -- see
    StaffUpdate's docstring. A manager can't target their own account here."""
    return await service.update_staff_member(current_user.care_home_id, current_user.id, user_id, payload)


@router.post("/staff/{user_id}/reset-password", response_model=StaffCredentials)
async def reset_staff_password(
    user_id: uuid.UUID,
    current_user: CurrentUser = Depends(require(Permission.MANAGE_USERS)),
    service: IdentityService = Depends(get_identity_service),
) -> StaffCredentials:
    """Generates a fresh one-time temporary password, same rule as creation: shown
    exactly once in the response, never recoverable afterwards."""
    return await service.reset_staff_password(current_user.care_home_id, current_user.id, user_id)