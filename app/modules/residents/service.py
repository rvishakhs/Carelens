from app.modules.residents.events import ResidentCreated
from app.modules.residents.models import Resident
from app.modules.residents.repository import ResidentRepository
from app.modules.residents.schemas import ResidentCreate
from app.shared.events import EventBus


class ResidentService:
    def __init__(self, repository: ResidentRepository, event_bus: EventBus):
        self._repository = repository
        self._event_bus = event_bus

    async def create_resident(self, care_home_id, actor_user_id, data: ResidentCreate) -> Resident:
        resident = Resident(care_home_id=care_home_id, **data.model_dump())
        resident = await self._repository.create(resident)
        await self._event_bus.publish(
            ResidentCreated(care_home_id=care_home_id, actor_user_id=actor_user_id, resident_id=resident.id)
        )
        return resident
