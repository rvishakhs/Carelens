import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request

from app.modules.floors.repository import FloorRepository
from app.modules.floors.schemas import FloorCreate, FloorRead, UserFloorLinkCreate
from app.modules.floors.service import FloorService
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.permissions import Permission, require
from app.modules.identity.schemas import CurrentUser
from app.shared.database import rls_session

router = APIRouter(prefix="/floors", tags=["floors"])


async def get_floor_repository(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncIterator[FloorRepository]:
    async with rls_session(current_user.care_home_id, current_user.id) as session:
        yield FloorRepository(session)


def get_floor_service(request: Request, repository: FloorRepository = Depends(get_floor_repository)) -> FloorService:
    return FloorService(repository, request.app.state.container.event_bus)


@router.post("", response_model=FloorRead, status_code=201)
async def create_floor(
    payload: FloorCreate,
    current_user: CurrentUser = Depends(require(Permission.MANAGE_FLOORS)),
    service: FloorService = Depends(get_floor_service),
) -> FloorRead:
    floor = await service.create_floor(current_user.care_home_id, current_user.id, payload)
    return FloorRead.model_validate(floor)


@router.get("", response_model=list[FloorRead])
async def list_floors(
    _: CurrentUser = Depends(require(Permission.VIEW_FLOORS)),
    repository: FloorRepository = Depends(get_floor_repository),
) -> list[FloorRead]:
    floors = await repository.list_active()
    return [FloorRead.model_validate(f) for f in floors]


@router.post("/access", status_code=204)
async def grant_floor_access(
    payload: UserFloorLinkCreate,
    current_user: CurrentUser = Depends(require(Permission.MANAGE_FLOORS)),
    service: FloorService = Depends(get_floor_service),
) -> None:
    await service.grant_access(current_user.care_home_id, current_user.id, payload.user_id, payload.floor_id)


@router.delete("/access", status_code=204)
async def revoke_floor_access(
    user_id: uuid.UUID,
    floor_id: uuid.UUID,
    current_user: CurrentUser = Depends(require(Permission.MANAGE_FLOORS)),
    service: FloorService = Depends(get_floor_service),
) -> None:
    await service.revoke_access(current_user.care_home_id, current_user.id, user_id, floor_id)
