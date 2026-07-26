import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.observations.models import Observation
from app.modules.observations.ports import ObservationReader
from app.modules.observations.schemas import ObservationSummary
from app.shared.exceptions import ConflictError


class ObservationRepository(ObservationReader):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_recent_for_resident(self, resident_id: uuid.UUID, hours: int = 24) -> list[ObservationSummary]:
        since = datetime.now(UTC) - timedelta(hours=hours)
        result = await self._session.execute(
            select(Observation)
            .where(
                Observation.resident_id == resident_id,
                Observation.recorded_at >= since,
                Observation.deleted_at.is_(None),
            )
            .order_by(Observation.recorded_at.desc())
        )
        return [ObservationSummary.model_validate(o) for o in result.scalars().all()]

    async def get_recent_for_residents(
        self, resident_ids: list[uuid.UUID], hours: int = 24
    ) -> dict[uuid.UUID, list[ObservationSummary]]:
        if not resident_ids:
            return {}
        since = datetime.now(UTC) - timedelta(hours=hours)
        result = await self._session.execute(
            select(Observation)
            .where(
                Observation.resident_id.in_(resident_ids),
                Observation.recorded_at >= since,
                Observation.deleted_at.is_(None),
            )
            .order_by(Observation.recorded_at.desc())
        )
        by_resident: dict[uuid.UUID, list[ObservationSummary]] = defaultdict(list)
        for o in result.scalars().all():
            by_resident[o.resident_id].append(ObservationSummary.model_validate(o))
        return dict(by_resident)

    async def create(self, observation: Observation) -> Observation:
        if observation.idempotency_key is not None:
            existing = await self._get_by_idempotency_key(observation.idempotency_key)
            if existing is not None:
                raise ConflictError(f"observation with idempotency_key {observation.idempotency_key!r} already exists")
        self._session.add(observation)
        await self._session.flush()
        return observation

    async def _get_by_idempotency_key(self, key: str) -> Observation | None:
        result = await self._session.execute(select(Observation).where(Observation.idempotency_key == key))
        return result.scalar_one_or_none()

    async def list_for_resident(self, resident_id: uuid.UUID, limit: int = 100) -> list[Observation]:
        result = await self._session.execute(
            select(Observation)
            .where(Observation.resident_id == resident_id, Observation.deleted_at.is_(None))
            .order_by(Observation.recorded_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
