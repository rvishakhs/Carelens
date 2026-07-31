import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request

from app.modules.care_recording.repository import CareRecordingRepository
from app.modules.care_recording.schemas import (
    CareCategoryRead,
    CareEventCreate,
    CareEventRead,
    CareTemplateRead,
)
from app.modules.care_recording.service import CareRecordingService
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.permissions import Permission, require
from app.modules.identity.schemas import CurrentUser
from app.shared.database import rls_session
from app.shared.exceptions import NotFoundError

router = APIRouter(prefix="/care-recording", tags=["care_recording"])


async def get_care_recording_repository(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncIterator[CareRecordingRepository]:
    async with rls_session(current_user.care_home_id, current_user.id, current_user.floor_ids) as session:
        yield CareRecordingRepository(session)


def get_care_recording_service(
    request: Request, repository: CareRecordingRepository = Depends(get_care_recording_repository)
) -> CareRecordingService:
    return CareRecordingService(repository, request.app.state.container.event_bus)


@router.get("/categories", response_model=list[CareCategoryRead])
async def list_categories(
    _: CurrentUser = Depends(require(Permission.RECORD_CARE_EVENT)),
    repository: CareRecordingRepository = Depends(get_care_recording_repository),
) -> list[CareCategoryRead]:
    return [CareCategoryRead.model_validate(c) for c in await repository.list_categories()]


@router.get("/categories/{category_id}/templates", response_model=list[CareTemplateRead])
async def list_templates(
    category_id: uuid.UUID,
    _: CurrentUser = Depends(require(Permission.RECORD_CARE_EVENT)),
    repository: CareRecordingRepository = Depends(get_care_recording_repository),
) -> list[CareTemplateRead]:
    templates = await repository.list_templates_by_category(category_id)
    return [CareTemplateRead.model_validate(t) for t in templates]


@router.get("/templates/{template_id}", response_model=CareTemplateRead)
async def get_template(
    template_id: uuid.UUID,
    _: CurrentUser = Depends(require(Permission.RECORD_CARE_EVENT)),
    repository: CareRecordingRepository = Depends(get_care_recording_repository),
) -> CareTemplateRead:
    template = await repository.get_template_detail(template_id)
    if template is None:
        raise NotFoundError(f"care template {template_id} not found")
    return CareTemplateRead.model_validate(template)


@router.post("/events", response_model=CareEventRead, status_code=201)
async def record_care_event(
    payload: CareEventCreate,
    current_user: CurrentUser = Depends(require(Permission.RECORD_CARE_EVENT)),
    service: CareRecordingService = Depends(get_care_recording_service),
) -> CareEventRead:
    event = await service.record_care_event(current_user.care_home_id, current_user.id, payload)
    return CareEventRead.model_validate(event)


@router.get("/residents/{resident_id}/events", response_model=list[CareEventRead])
async def list_resident_events(
    resident_id: uuid.UUID,
    _: CurrentUser = Depends(require(Permission.RECORD_CARE_EVENT)),
    repository: CareRecordingRepository = Depends(get_care_recording_repository),
) -> list[CareEventRead]:
    events = await repository.list_for_resident(resident_id)
    return [CareEventRead.model_validate(e) for e in events]
