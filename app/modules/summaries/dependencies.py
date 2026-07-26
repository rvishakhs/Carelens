"""Public dependency-provider surface -- `handover` imports SummaryReader from ports.py
and get_summary_reader from here, never summaries.repository or summaries.models."""

from collections.abc import AsyncIterator

from fastapi import Depends, Request

from app.modules.ai_gateway.dependencies import get_ai_gateway_service
from app.modules.ai_gateway.service import AIGatewayService
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.schemas import CurrentUser
from app.modules.observations.dependencies import get_observation_reader
from app.modules.observations.ports import ObservationReader
from app.modules.residents.dependencies import get_resident_reader
from app.modules.residents.ports import ResidentReader
from app.modules.summaries.ports import SummaryReader
from app.modules.summaries.repository import SummaryRepository
from app.modules.summaries.service import SummaryService
from app.shared.database import rls_session


async def get_summary_reader(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncIterator[SummaryReader]:
    async with rls_session(current_user.care_home_id, current_user.id) as session:
        yield SummaryRepository(session)


async def get_summary_repository(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncIterator[SummaryRepository]:
    async with rls_session(current_user.care_home_id, current_user.id) as session:
        yield SummaryRepository(session)


def get_summary_service(
    request: Request,
    repository: SummaryRepository = Depends(get_summary_repository),
    observation_reader: ObservationReader = Depends(get_observation_reader),
    resident_reader: ResidentReader = Depends(get_resident_reader),
    ai_gateway: AIGatewayService = Depends(get_ai_gateway_service),
) -> SummaryService:
    return SummaryService(
        repository, observation_reader, resident_reader, ai_gateway, request.app.state.container.event_bus
    )
