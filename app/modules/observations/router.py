import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import AwareDatetime

from app import (
    CurrentUser,
    ObservationCreate,
    ObservationRead,
    ObservationRepository,
    ObservationService,
    Permission,
    get_current_user,
    require,
    rls_session,
)
from app.modules.observations.models import ObservationType

router = APIRouter(prefix="/observations", tags=["observations"])


async def get_observation_repository(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncIterator[ObservationRepository]:
    async with rls_session(current_user.care_home_id, current_user.id, current_user.floor_ids) as session:
        yield ObservationRepository(session)


def get_observation_service(
    request: Request, repository: ObservationRepository = Depends(get_observation_repository)
) -> ObservationService:
    container = request.app.state.container
    return ObservationService(repository, container.event_bus, container.note_structurer)


@router.post("", response_model=ObservationRead, status_code=201)
async def create_observation(
    payload: ObservationCreate,
    current_user: CurrentUser = Depends(require(Permission.CREATE_OBSERVATION)),
    service: ObservationService = Depends(get_observation_service),
) -> ObservationRead:
    observation = await service.record_observation(current_user.care_home_id, current_user.id, payload)
    return ObservationRead.model_validate(observation)


@router.post("/batch", response_model=list[ObservationRead], status_code=201)
async def create_observations_batch(
    payloads: list[ObservationCreate],
    current_user: CurrentUser = Depends(require(Permission.CREATE_OBSERVATION)),
    service: ObservationService = Depends(get_observation_service),
) -> list[ObservationRead]:
    results = [await service.record_observation(current_user.care_home_id, current_user.id, p) for p in payloads]
    return [ObservationRead.model_validate(o) for o in results]


@router.get("", response_model=list[ObservationRead])
async def list_observations(
    resident_id: uuid.UUID,
    type: ObservationType | None = None,
    since: AwareDatetime | None = None,
    until: AwareDatetime | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: CurrentUser = Depends(require(Permission.VIEW_OBSERVATION)),
    repository: ObservationRepository = Depends(get_observation_repository),
) -> list[ObservationRead]:
    if since is not None and until is not None and since >= until:
        raise HTTPException(status_code=422, detail="since must be earlier than until")
    return await repository.list_for_resident(
        resident_id,
        limit,
        offset=offset,
        since=since,
        until=until,
        observation_type=type,
    )


@router.get("/sources/{source_type}/{source_id}", response_model=ObservationRead)
async def get_observation_source(
    source_type: str,
    source_id: uuid.UUID,
    resident_id: uuid.UUID,
    _: CurrentUser = Depends(require(Permission.VIEW_OBSERVATION)),
    repository: ObservationRepository = Depends(get_observation_repository),
) -> ObservationRead:
    source = await repository.get_source(resident_id, source_type, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="observation source not found")
    return source
