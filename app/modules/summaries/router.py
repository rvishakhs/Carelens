import uuid

from fastapi import APIRouter, Depends

from app.modules.identity.permissions import Permission, require
from app.modules.identity.schemas import CurrentUser
from app.modules.summaries.dependencies import get_summary_service
from app.modules.summaries.schemas import SummaryFeedbackCreate, SummaryRead
from app.modules.summaries.service import SummaryService

router = APIRouter(prefix="/summaries", tags=["summaries"])


@router.post("/{resident_id}/generate", response_model=SummaryRead, status_code=201)
async def generate_summary(
    resident_id: uuid.UUID,
    current_user: CurrentUser = Depends(require(Permission.VIEW_SUMMARY)),
    service: SummaryService = Depends(get_summary_service),
) -> SummaryRead:
    """Manual trigger for dev/demo -- the scheduled path is workers/jobs/summary_job.py."""
    output = await service.generate_daily_summary(current_user.care_home_id, resident_id)
    return SummaryRead.model_validate(output)


@router.post("/{summary_id}/feedback", response_model=SummaryRead)
async def submit_feedback(
    summary_id: uuid.UUID,
    payload: SummaryFeedbackCreate,
    current_user: CurrentUser = Depends(require(Permission.SUBMIT_SUMMARY_FEEDBACK)),
    service: SummaryService = Depends(get_summary_service),
) -> SummaryRead:
    output = await service.submit_feedback(current_user.care_home_id, current_user.id, summary_id, payload)
    return SummaryRead.model_validate(output)
