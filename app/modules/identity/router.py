from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request

from app.modules.identity.dependencies import get_current_user
from app.modules.identity.permissions import Permission, require
from app.modules.identity.repository import UserRepository
from app.modules.identity.schemas import CurrentUser, StaffCreate, StaffCreated, UserRead
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
    users = await repository.list_active()
    return [UserRead.model_validate(u) for u in users]