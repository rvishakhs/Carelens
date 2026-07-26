from fastapi import APIRouter, Depends

from app.modules.ai_gateway.dependencies import get_ai_gateway_service
from app.modules.ai_gateway.schemas import GatewayTestRequest, GatewayTestResponse
from app.modules.ai_gateway.service import AIGatewayService
from app.modules.identity.permissions import Permission, require
from app.modules.identity.schemas import CurrentUser

router = APIRouter(prefix="/ai-gateway", tags=["ai_gateway"])


@router.post("/test-completion", response_model=GatewayTestResponse)
async def test_completion(
    payload: GatewayTestRequest,
    current_user: CurrentUser = Depends(require(Permission.MANAGE_USERS)),
    service: AIGatewayService = Depends(get_ai_gateway_service),
) -> GatewayTestResponse:
    """Dev/ops utility proving the pseudonymise -> LLM -> re-identify path works
    end-to-end against the configured provider. Manager-only; not part of any
    clinical workflow."""
    result = await service.complete(
        care_home_id=current_user.care_home_id,
        resident_id=payload.resident_id,
        resident_display_name=payload.resident_display_name,
        prompt=payload.prompt,
    )
    return GatewayTestResponse(result=result)
