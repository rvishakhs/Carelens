from fastapi import APIRouter, Depends, Request

from app.modules.identity.dependencies import get_current_user
from app.modules.identity.schemas import CurrentUser
from app.modules.identity.service import IdentityService

router = APIRouter(prefix="/identity", tags=["identity"])


def get_identity_service(request: Request) -> IdentityService:
    return IdentityService(request.app.state.container.event_bus)


@router.get("/me", response_model=CurrentUser)
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),
    service: IdentityService = Depends(get_identity_service),
) -> CurrentUser:
    await service.record_login(current_user)
    return current_user