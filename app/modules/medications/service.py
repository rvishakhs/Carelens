import uuid
from datetime import UTC, datetime

from app.modules.medications.events import MedicationEventRecorded
from app.modules.medications.models import Medication, MedicationEvent
from app.modules.medications.repository import MedicationRepository
from app.modules.medications.schemas import MedicationCreate, MedicationEventCreate
from app.shared.events import EventBus
from app.shared.exceptions import NotFoundError


class MedicationService:
    def __init__(self, repository: MedicationRepository, event_bus: EventBus):
        self._repository = repository
        self._event_bus = event_bus

    async def create_medication(self, care_home_id: uuid.UUID, data: MedicationCreate) -> Medication:
        medication = Medication(care_home_id=care_home_id, **data.model_dump())
        return await self._repository.create(medication)

    async def record_event(
        self, care_home_id: uuid.UUID, actor_user_id: uuid.UUID, medication_id: uuid.UUID, data: MedicationEventCreate
    ) -> MedicationEvent:
        medication = await self._repository.get_by_id(medication_id)
        if medication is None:
            raise NotFoundError(f"medication {medication_id} not found")

        event = MedicationEvent(
            care_home_id=care_home_id,
            medication_id=medication_id,
            resident_id=medication.resident_id,
            status=data.status,
            scheduled_at=data.scheduled_at,
            recorded_at=datetime.now(UTC),
            recorded_by=actor_user_id,
            notes=data.notes,
        )
        event = await self._repository.record_event(event)

        await self._event_bus.publish(
            MedicationEventRecorded(
                care_home_id=care_home_id,
                actor_user_id=actor_user_id,
                medication_event_id=event.id,
                resident_id=event.resident_id,
                status=event.status,
            )
        )
        return event
