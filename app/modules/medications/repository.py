import uuid
from datetime import date

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.medications.models import Medication, MedicationEvent
from app.modules.medications.ports import MedicationReader
from app.modules.medications.schemas import MedicationRead, MedicationScheduleEntry

# administered/self_administered read as "given"; anything the resident didn't
# actually receive reads as "missed" -- collapsing the DB's 6-value status into the
# tri-state MedicationsPage renders (given/due/missed).
_GIVEN_STATUSES = {"administered", "self_administered"}


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

    async def get_schedule_for_latest_day(self) -> tuple[date | None, list[MedicationScheduleEntry]]:
        """No ORM model spans medications + medication_events + residents in one
        shape, and this is read-only, so it's a raw query -- runs through the same
        RLS-scoped session as everything else here, so tenant/floor filtering is
        already enforced by Postgres, not re-implemented here.

        "Latest day" rather than literal calendar-today: synthdata's generated
        history ends the day before the run date, so a strict today filter would
        always be empty against a freshly generated dataset.
        """
        latest_day = (
            await self._session.execute(text("SELECT max(COALESCE(scheduled_for, administered_at))::date FROM medication_events"))
        ).scalar_one_or_none()
        if latest_day is None:
            return None, []

        rows = (
            await self._session.execute(
                text(
                    """
                    SELECT
                        me.id AS medication_event_id, me.medication_id, me.resident_id,
                        r.first_name || ' ' || r.last_name AS resident_display_name,
                        m.drug_name, m.dose, me.scheduled_for, me.status
                    FROM medication_events me
                    JOIN medications m ON m.id = me.medication_id
                    JOIN residents r ON r.id = me.resident_id
                    WHERE COALESCE(me.scheduled_for, me.administered_at)::date = :day
                    ORDER BY me.scheduled_for NULLS LAST, resident_display_name
                    """
                ),
                {"day": latest_day},
            )
        ).mappings()

        entries = [
            MedicationScheduleEntry(
                medication_event_id=row["medication_event_id"],
                medication_id=row["medication_id"],
                resident_id=row["resident_id"],
                resident_display_name=row["resident_display_name"],
                drug_name=row["drug_name"],
                dose=row["dose"],
                scheduled_for=row["scheduled_for"],
                status="given" if row["status"] in _GIVEN_STATUSES else "missed",
            )
            for row in rows
        ]
        return latest_day, entries
