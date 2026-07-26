import uuid

from app.modules.observations.events import ObservationRecorded
from app.modules.observations.models import Observation, ObservationType
from app.modules.observations.ports import NoteStructurer
from app.modules.observations.repository import ObservationRepository
from app.modules.observations.schemas import ObservationCreate, is_plausible
from app.shared.events import EventBus


class ObservationService:
    def __init__(self, repository: ObservationRepository, event_bus: EventBus, note_structurer: NoteStructurer):
        self._repository = repository
        self._event_bus = event_bus
        self._note_structurer = note_structurer

    async def record_observation(
        self, care_home_id: uuid.UUID, actor_user_id: uuid.UUID, data: ObservationCreate
    ) -> Observation:
        value = dict(data.value)
        if data.type is ObservationType.NOTE:
            value["structured"] = await self._note_structurer.structure(value["text"])

        observation = Observation(
            care_home_id=care_home_id,
            resident_id=data.resident_id,
            type=data.type,
            value=value,
            recorded_at=data.recorded_at,
            recorded_by=actor_user_id,
            is_implausible=not is_plausible(data.type, data.value),
            idempotency_key=data.idempotency_key,
        )
        observation = await self._repository.create(observation)

        await self._event_bus.publish(
            ObservationRecorded(
                care_home_id=care_home_id,
                actor_user_id=actor_user_id,
                observation_id=observation.id,
                resident_id=observation.resident_id,
                type=observation.type,
                is_implausible=observation.is_implausible,
            )
        )
        return observation
