import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request

from app.modules.identity.dependencies import get_current_user
from app.modules.identity.permissions import Permission, require
from app.modules.identity.schemas import CurrentUser
from app.modules.residents.repository import ResidentRepository
from app.modules.residents.schemas import ResidentCreate, ResidentRead
from app.modules.residents.service import ResidentService
from app.shared.database import rls_session
from app.shared.exceptions import NotFoundError

router = APIRouter(prefix="/residents", tags=["residents"])


async def get_resident_repository(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncIterator[ResidentRepository]:
    async with rls_session(current_user.care_home_id, current_user.id, current_user.floor_ids) as session:
        yield ResidentRepository(session)


def get_resident_service(
    request: Request, repository: ResidentRepository = Depends(get_resident_repository)
) -> ResidentService:
    return ResidentService(repository, request.app.state.container.event_bus)


@router.post("", response_model=ResidentRead, status_code=201)
async def create_resident(
    payload: ResidentCreate,
    current_user: CurrentUser = Depends(require(Permission.MANAGE_USERS)),
    service: ResidentService = Depends(get_resident_service),
) -> ResidentRead:
    resident = await service.create_resident(current_user.care_home_id, current_user.id, payload)
    return ResidentRead.model_validate(resident)


@router.get("", response_model=list[ResidentRead])
async def list_residents(
    _: CurrentUser = Depends(require(Permission.VIEW_RESIDENT)),
    repository: ResidentRepository = Depends(get_resident_repository),
) -> list[ResidentRead]:
    residents = await repository.list_active()
    return [ResidentRead.model_validate(r) for r in residents]


@router.get("/{resident_id}", response_model=ResidentRead)
async def get_resident(
    resident_id: uuid.UUID,
    _: CurrentUser = Depends(require(Permission.VIEW_RESIDENT)),
    repository: ResidentRepository = Depends(get_resident_repository),
) -> ResidentRead:
    resident = await repository.get_by_id(resident_id)
    if resident is None:
        raise NotFoundError(f"resident {resident_id} not found")
    return ResidentRead.model_validate(resident)
