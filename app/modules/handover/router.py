from fastapi import APIRouter, Depends, Request

from app.modules.handover.schemas import HandoverResidentCard
from app.modules.handover.service import HandoverService
from app.modules.identity.permissions import Permission, require
from app.modules.identity.schemas import CurrentUser
from app.modules.observations.dependencies import get_observation_reader
from app.modules.observations.ports import ObservationReader
from app.modules.residents.dependencies import get_resident_reader
from app.modules.residents.ports import ResidentReader
from app.modules.summaries.dependencies import get_summary_reader
from app.modules.summaries.ports import SummaryReader

router = APIRouter(prefix="/handover", tags=["handover"])


def get_handover_service(
    request: Request,
    resident_reader: ResidentReader = Depends(get_resident_reader),
    observation_reader: ObservationReader = Depends(get_observation_reader),
    summary_reader: SummaryReader = Depends(get_summary_reader),
) -> HandoverService:
    container = request.app.state.container
    return HandoverService(
        resident_reader, observation_reader, summary_reader, container.attention_ranker, container.event_bus
    )


@router.get("", response_model=list[HandoverResidentCard])
async def get_handover_view(
    current_user: CurrentUser = Depends(require(Permission.VIEW_HANDOVER)),
    service: HandoverService = Depends(get_handover_service),
) -> list[HandoverResidentCard]:
    return await service.get_handover_view(current_user.care_home_id, current_user.id)
