"""Public dependency-provider surface -- `summaries` imports AIGatewayService from
service.py and get_ai_gateway_service from here, never repository.py or models.py."""

from collections.abc import AsyncIterator

from fastapi import Depends, Request

from app.modules.ai_gateway.pseudonymiser import Pseudonymiser
from app.modules.ai_gateway.repository import PseudonymMappingRepository
from app.modules.ai_gateway.service import AIGatewayService
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.schemas import CurrentUser
from app.shared.database import rls_session


async def get_ai_gateway_service(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncIterator[AIGatewayService]:
    container = request.app.state.container
    async with rls_session(current_user.care_home_id, current_user.id) as session:
        mapping_repository = PseudonymMappingRepository(session, container.settings.secret_key)
        yield AIGatewayService(container.llm_provider, Pseudonymiser(mapping_repository))
