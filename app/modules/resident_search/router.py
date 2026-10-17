import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request

from app import CurrentUser, Permission, get_current_user, get_floor_scope, require, rls_session
from app.modules.resident_search.repository import ResidentSearchRepository
from app.modules.resident_search.schemas import (
    ResidentSearchRequest,
    ResidentSearchResponse,
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
)
async def search_resident_history(
    resident_id: uuid.UUID,
    payload: ResidentSearchRequest,
    current_user: CurrentUser = Depends(require(Permission.SEARCH_RESIDENT_HISTORY)),
    service: ResidentSearchService = Depends(get_resident_search_service),
) -> ResidentSearchResponse:
    return await service.search(current_user.care_home_id, current_user.id, resident_id, payload)
