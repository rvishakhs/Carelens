import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.medications.models import Medication, MedicationEvent
from app.modules.medications.ports import MedicationReader
from app.modules.medications.schemas import MedicationRead


class MedicationRepository(MedicationReader):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_for_resident(self, resident_id: uuid.UUID) -> list[MedicationRead]:
        result = await self._session.execute(
            select(Medication).where(Medication.resident_id == resident_id, Medication.deleted_at.is_(None))
        )
        return [MedicationRead.model_validate(m) for m in result.scalars().all()]

    async def create(self, medication: Medication) -> Medication:
        self._session.add(medication)
        await self._session.flush()
        return medication

    async def get_by_id(self, medication_id: uuid.UUID) -> Medication | None:
        return await self._session.get(Medication, medication_id)

    async def record_event(self, event: MedicationEvent) -> MedicationEvent:
        self._session.add(event)
        await self._session.flush()
        return event
