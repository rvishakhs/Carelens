import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request

from app.modules.identity.dependencies import get_current_user
from app.modules.identity.permissions import Permission, require
from app.modules.identity.schemas import CurrentUser
from app.modules.observations.repository import ObservationRepository
from app.modules.observations.schemas import ObservationCreate, ObservationRead
from app.modules.observations.service import ObservationService
from app.shared.database import rls_session

router = APIRouter(prefix="/observations", tags=["observations"])


async def get_observation_repository(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncIterator[ObservationRepository]:
    async with rls_session(current_user.care_home_id, current_user.id) as session:
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
    _: CurrentUser = Depends(require(Permission.VIEW_OBSERVATION)),
    repository: ObservationRepository = Depends(get_observation_repository),
) -> list[ObservationRead]:
    observations = await repository.list_for_resident(resident_id)
    return [ObservationRead.model_validate(o) for o in observations]
