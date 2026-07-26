import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request

from app.modules.identity.dependencies import get_current_user
from app.modules.identity.permissions import Permission, require
from app.modules.identity.schemas import CurrentUser
from app.modules.medications.repository import MedicationRepository
from app.modules.medications.schemas import MedicationCreate, MedicationEventCreate, MedicationEventRead, MedicationRead
from app.modules.medications.service import MedicationService
from app.shared.database import rls_session

router = APIRouter(prefix="/medications", tags=["medications"])


async def get_medication_repository(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncIterator[MedicationRepository]:
    async with rls_session(current_user.care_home_id, current_user.id) as session:
        yield MedicationRepository(session)


def get_medication_service(
    request: Request, repository: MedicationRepository = Depends(get_medication_repository)
) -> MedicationService:
    return MedicationService(repository, request.app.state.container.event_bus)


@router.post("", response_model=MedicationRead, status_code=201)
async def create_medication(
    payload: MedicationCreate,
    current_user: CurrentUser = Depends(require(Permission.MANAGE_MEDICATIONS)),
    service: MedicationService = Depends(get_medication_service),
) -> MedicationRead:
    medication = await service.create_medication(current_user.care_home_id, payload)
    return MedicationRead.model_validate(medication)


@router.get("", response_model=list[MedicationRead])
async def list_medications(
    resident_id: uuid.UUID,
    _: CurrentUser = Depends(require(Permission.VIEW_MEDICATIONS)),
    repository: MedicationRepository = Depends(get_medication_repository),
) -> list[MedicationRead]:
    return await repository.list_for_resident(resident_id)


@router.post("/{medication_id}/events", response_model=MedicationEventRead, status_code=201)
async def record_medication_event(
    medication_id: uuid.UUID,
    payload: MedicationEventCreate,
    current_user: CurrentUser = Depends(require(Permission.MANAGE_MEDICATIONS)),
    service: MedicationService = Depends(get_medication_service),
) -> MedicationEventRead:
    event = await service.record_event(current_user.care_home_id, current_user.id, medication_id, payload)
    return MedicationEventRead.model_validate(event)
