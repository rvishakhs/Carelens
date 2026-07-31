import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request

from app.modules.ai_insights.repository import AIInsightRepository
from app.modules.ai_insights.schemas import (
    AlertAcknowledgeRequest,
    ResidentAIAlertRead,
    ResidentAIReportRead,
    ResidentAISummaryRead,
    ResidentPredictionRead,
    SummaryFeedbackCreate,
)
from app.modules.ai_insights.service import AIInsightService
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.permissions import Permission, require
from app.modules.identity.schemas import CurrentUser
from app.shared.database import rls_session

router = APIRouter(prefix="/ai-insights", tags=["ai_insights"])


async def get_ai_insight_repository(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncIterator[AIInsightRepository]:
    async with rls_session(current_user.care_home_id, current_user.id, current_user.floor_ids) as session:
        yield AIInsightRepository(session)


def get_ai_insight_service(
    request: Request, repository: AIInsightRepository = Depends(get_ai_insight_repository)
) -> AIInsightService:
    return AIInsightService(repository, request.app.state.container.event_bus)


@router.get("/residents/{resident_id}/summaries", response_model=list[ResidentAISummaryRead])
async def list_summaries(
    resident_id: uuid.UUID,
    _: CurrentUser = Depends(require(Permission.VIEW_AI_INSIGHTS)),
    repository: AIInsightRepository = Depends(get_ai_insight_repository),
) -> list[ResidentAISummaryRead]:
    return [ResidentAISummaryRead.model_validate(s) for s in await repository.list_summaries(resident_id)]


@router.get("/residents/{resident_id}/reports", response_model=list[ResidentAIReportRead])
async def list_reports(
    resident_id: uuid.UUID,
    _: CurrentUser = Depends(require(Permission.VIEW_AI_INSIGHTS)),
    repository: AIInsightRepository = Depends(get_ai_insight_repository),
) -> list[ResidentAIReportRead]:
    return [ResidentAIReportRead.model_validate(r) for r in await repository.list_reports(resident_id)]


@router.get("/residents/{resident_id}/alerts", response_model=list[ResidentAIAlertRead])
async def list_alerts(
    resident_id: uuid.UUID,
    _: CurrentUser = Depends(require(Permission.VIEW_AI_INSIGHTS)),
    repository: AIInsightRepository = Depends(get_ai_insight_repository),
) -> list[ResidentAIAlertRead]:
    return [ResidentAIAlertRead.model_validate(a) for a in await repository.list_alerts(resident_id)]


@router.get("/residents/{resident_id}/predictions", response_model=list[ResidentPredictionRead])
async def list_predictions(
    resident_id: uuid.UUID,
    _: CurrentUser = Depends(require(Permission.VIEW_AI_INSIGHTS)),
    repository: AIInsightRepository = Depends(get_ai_insight_repository),
) -> list[ResidentPredictionRead]:
    return [ResidentPredictionRead.model_validate(p) for p in await repository.list_predictions(resident_id)]


@router.post("/summaries/{summary_id}/feedback", response_model=ResidentAISummaryRead)
async def submit_summary_feedback(
    summary_id: uuid.UUID,
    payload: SummaryFeedbackCreate,
    current_user: CurrentUser = Depends(require(Permission.VIEW_AI_INSIGHTS)),
    service: AIInsightService = Depends(get_ai_insight_service),
) -> ResidentAISummaryRead:
    summary = await service.submit_summary_feedback(current_user.care_home_id, current_user.id, summary_id, payload)
    return ResidentAISummaryRead.model_validate(summary)


@router.post("/alerts/{alert_id}/acknowledge", response_model=ResidentAIAlertRead)
async def acknowledge_alert(
    alert_id: uuid.UUID,
    payload: AlertAcknowledgeRequest,
    current_user: CurrentUser = Depends(require(Permission.MANAGE_AI_ALERTS)),
    service: AIInsightService = Depends(get_ai_insight_service),
) -> ResidentAIAlertRead:
    alert = await service.acknowledge_alert(current_user.care_home_id, current_user.id, alert_id, payload)
    return ResidentAIAlertRead.model_validate(alert)
