"""Public dependency-provider surface -- `summaries` imports AIGatewayService from
service.py and get_ai_gateway_service from here, never repository.py or models.py."""

from collections.abc import AsyncIterator

from fastapi import Depends, Request

from app import Pseudonymiser
from app import PseudonymMappingRepository
from app import AIGatewayService
from app import get_current_user
from app import CurrentUser
from app import rls_session


async def get_ai_gateway_service(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncIterator[AIGatewayService]:
    container = request.app.state.container
    async with rls_session(current_user.care_home_id, current_user.id, current_user.floor_ids) as session:
        mapping_repository = PseudonymMappingRepository(session, container.settings.secret_key)
        yield AIGatewayService(container.llm_provider, Pseudonymiser(mapping_repository))
