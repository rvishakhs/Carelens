import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request, status

from app import CurrentUser, Permission, get_current_user, get_floor_scope, require, rls_session
from app.modules.resident_search.repository import ResidentSearchRepository
from app.modules.resident_search.schemas import (
    ResidentSearchRequest,
    ResidentSearchResponse,
    ResidentSearchSourceResponse,
    SearchSourceType,
)
from app.modules.resident_search.service import ResidentSearchService

router = APIRouter(prefix="/residents", tags=["resident-search"])


async def get_resident_search_repository(
    current_user: CurrentUser = Depends(get_current_user),
    floor_ids: list[uuid.UUID] = Depends(get_floor_scope),
) -> AsyncIterator[ResidentSearchRepository]:
    async with rls_session(
        current_user.care_home_id,
        current_user.id,
        floor_ids,
    ) as session:
        yield ResidentSearchRepository(session)


def get_resident_search_service(
    request: Request,
    repository: ResidentSearchRepository = Depends(get_resident_search_repository),
) -> ResidentSearchService:
    return ResidentSearchService(repository, request.app.state.container.event_bus)


@router.post(
    "/{resident_id}/history-search",
    response_model=ResidentSearchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def search_resident_history(
    resident_id: uuid.UUID,
    payload: ResidentSearchRequest,
    current_user: CurrentUser = Depends(require(Permission.SEARCH_RESIDENT_HISTORY)),
    service: ResidentSearchService = Depends(get_resident_search_service),
) -> ResidentSearchResponse:
    return await service.search(current_user.care_home_id, current_user.id, resident_id, payload)


@router.get(
    "/{resident_id}/history-search/{search_id}",
    response_model=ResidentSearchResponse,
)
async def get_resident_history_search(
    resident_id: uuid.UUID,
    search_id: uuid.UUID,
    current_user: CurrentUser = Depends(require(Permission.SEARCH_RESIDENT_HISTORY)),
    service: ResidentSearchService = Depends(get_resident_search_service),
) -> ResidentSearchResponse:
    del current_user
    return await service.get_saved_search(resident_id, search_id)


@router.get(
    "/{resident_id}/history-search/{search_id}/sources/{source_type}/{source_id}",
    response_model=ResidentSearchSourceResponse,
)
async def get_resident_history_search_source(
    resident_id: uuid.UUID,
    search_id: uuid.UUID,
    source_type: SearchSourceType,
    source_id: uuid.UUID,
    current_user: CurrentUser = Depends(require(Permission.SEARCH_RESIDENT_HISTORY)),
    service: ResidentSearchService = Depends(get_resident_search_service),
) -> ResidentSearchSourceResponse:
    del current_user
    return await service.get_source(resident_id, search_id, source_type, source_id)
