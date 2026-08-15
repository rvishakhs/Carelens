import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request

from app.modules.identity.dependencies import get_current_user, get_floor_scope
from app.modules.identity.permissions import Permission, require
from app.modules.identity.schemas import CurrentUser
from app.modules.residents.detail_repository import ResidentDetailRepository
from app.modules.residents.repository import ResidentRepository
from app.modules.residents.schemas import (
    ActivityEntry,
    CarePlanRead,
    CareRecordEntry,
    ResidentCreate,
    ResidentListItem,
    ResidentOverview,
    ResidentRead,
)
from app.modules.residents.service import ResidentService
from app.shared.database import rls_session
from app.shared.exceptions import NotFoundError

router = APIRouter(prefix="/residents", tags=["residents"])
care_plans_router = APIRouter(prefix="/care-plans", tags=["residents"])


async def get_resident_repository(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncIterator[ResidentRepository]:
    """Full-authorisation session -- for writes. A create must stay scoped to every
    floor the user is authorised for (not whatever they've narrowed *viewing* to via
    get_floor_scope), or the ORM's INSERT...RETURNING can't see the row it just
    created on a floor outside that narrower scope (see ResidentCreate's
    docstring)."""
    async with rls_session(current_user.care_home_id, current_user.id, current_user.floor_ids) as session:
        yield ResidentRepository(session)


async def get_resident_repository_scoped(
    current_user: CurrentUser = Depends(get_current_user),
    floor_ids: list[uuid.UUID] = Depends(get_floor_scope),
) -> AsyncIterator[ResidentRepository]:
    """View session -- honours the caller's optional ?floor_id= (get_floor_scope),
    defaulting to every authorised floor. For reads only."""
    async with rls_session(current_user.care_home_id, current_user.id, floor_ids) as session:
        yield ResidentRepository(session)


async def get_resident_detail_repository(
    current_user: CurrentUser = Depends(get_current_user),
    floor_ids: list[uuid.UUID] = Depends(get_floor_scope),
) -> AsyncIterator[ResidentDetailRepository]:
    async with rls_session(current_user.care_home_id, current_user.id, floor_ids) as session:
        yield ResidentDetailRepository(session)


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


@router.get("", response_model=list[ResidentListItem])
async def list_residents(
    _: CurrentUser = Depends(require(Permission.VIEW_RESIDENT)),
    repository: ResidentDetailRepository = Depends(get_resident_detail_repository),
) -> list[ResidentListItem]:
    return await repository.list_with_summary()


@router.get("/{resident_id}", response_model=ResidentRead)
async def get_resident(
    resident_id: uuid.UUID,
    _: CurrentUser = Depends(require(Permission.VIEW_RESIDENT)),
    repository: ResidentRepository = Depends(get_resident_repository_scoped),
) -> ResidentRead:
    resident = await repository.get_by_id(resident_id)
    if resident is None:
        raise NotFoundError(f"resident {resident_id} not found")
    return ResidentRead.model_validate(resident)


@router.get("/{resident_id}/overview", response_model=ResidentOverview)
async def get_resident_overview(
    resident_id: uuid.UUID,
    _: CurrentUser = Depends(require(Permission.VIEW_RESIDENT)),
    repository: ResidentDetailRepository = Depends(get_resident_detail_repository),
) -> ResidentOverview:
    overview = await repository.get_overview(resident_id)
    if overview is None:
        raise NotFoundError(f"resident {resident_id} not found")
    return overview


@router.get("/{resident_id}/care-plan", response_model=list[CarePlanRead])
async def get_resident_care_plan(
    resident_id: uuid.UUID,
    _: CurrentUser = Depends(require(Permission.VIEW_RESIDENT)),
    repository: ResidentDetailRepository = Depends(get_resident_detail_repository),
) -> list[CarePlanRead]:
    return await repository.get_care_plan(resident_id)


@router.get("/{resident_id}/care-records", response_model=list[CareRecordEntry])
async def get_resident_care_records(
    resident_id: uuid.UUID,
    _: CurrentUser = Depends(require(Permission.VIEW_OBSERVATION)),
    repository: ResidentDetailRepository = Depends(get_resident_detail_repository),
) -> list[CareRecordEntry]:
    return await repository.get_care_records(resident_id)


@router.get("/{resident_id}/activity", response_model=list[ActivityEntry])
async def get_resident_activity(
    resident_id: uuid.UUID,
    _: CurrentUser = Depends(require(Permission.VIEW_RESIDENT)),
    repository: ResidentDetailRepository = Depends(get_resident_detail_repository),
) -> list[ActivityEntry]:
    return await repository.get_activity(resident_id)


@care_plans_router.get("", response_model=list[CarePlanRead])
async def list_all_care_plans(
    _: CurrentUser = Depends(require(Permission.VIEW_RESIDENT)),
    repository: ResidentDetailRepository = Depends(get_resident_detail_repository),
) -> list[CarePlanRead]:
    return await repository.list_active_care_plans()
