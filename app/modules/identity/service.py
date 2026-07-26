from app.modules.identity.events import UserLoggedIn
from app.modules.identity.schemas import CurrentUser
from app.shared.events import EventBus


class IdentityService:
    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus

    async def record_login(self, user: CurrentUser) -> None:
        await self._event_bus.publish(
            UserLoggedIn(care_home_id=user.care_home_id, actor_user_id=user.id, user_id=user.id, role=user.role.value)
        )