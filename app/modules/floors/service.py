import uuid

from app.modules.floors.events import FloorCreated, UserFloorAccessGranted, UserFloorAccessRevoked
from app.modules.floors.models import Floor
from app.modules.floors.repository import FloorRepository
from app.modules.floors.schemas import FloorCreate
from app.shared.events import EventBus


class FloorService:
    def __init__(self, repository: FloorRepository, event_bus: EventBus):
        self._repository = repository
        self._event_bus = event_bus

    async def create_floor(self, care_home_id: uuid.UUID, actor_user_id: uuid.UUID, data: FloorCreate) -> Floor:
        floor = Floor(care_home_id=care_home_id, **data.model_dump())
        floor = await self._repository.create(floor)
        await self._event_bus.publish(
            FloorCreated(care_home_id=care_home_id, actor_user_id=actor_user_id, floor_id=floor.id)
        )
        return floor

    async def grant_access(
        self, care_home_id: uuid.UUID, actor_user_id: uuid.UUID, user_id: uuid.UUID, floor_id: uuid.UUID
    ) -> None:
        await self._repository.grant_access(care_home_id, user_id, floor_id, granted_by=actor_user_id)
        await self._event_bus.publish(
            UserFloorAccessGranted(
                care_home_id=care_home_id, actor_user_id=actor_user_id, user_id=user_id, floor_id=floor_id
            )
        )

    async def revoke_access(
        self, care_home_id: uuid.UUID, actor_user_id: uuid.UUID, user_id: uuid.UUID, floor_id: uuid.UUID
    ) -> None:
        await self._repository.revoke_access(user_id, floor_id)
        await self._event_bus.publish(
            UserFloorAccessRevoked(
                care_home_id=care_home_id, actor_user_id=actor_user_id, user_id=user_id, floor_id=floor_id
            )
        )
