import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import bindparam, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import ConflictError, NotFoundError, Observation, ObservationReader, ObservationSummary
from app.modules.observations.clinical_feed import CLINICAL_FEED_SQL, SOURCE_TYPES
from app.modules.observations.models import ObservationType
from app.modules.observations.schemas import ObservationRead, is_plausible


class ObservationRepository(ObservationReader):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def _read(
        self,
        resident_ids: list[uuid.UUID],
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        observation_type: ObservationType | None = None,
        limit: int | None = None,
        offset: int = 0,
        source_type: str | None = None,
        source_types: set[str] | None = None,
        source_id: uuid.UUID | None = None,
    ) -> list[ObservationRead]:
        if not resident_ids:
            return []
        clauses = ["resident_id IN :resident_ids"]
        params: dict = {"resident_ids": resident_ids}
        for name, value, clause in (
            ("since", since, "recorded_at >= :since"),
            ("until", until, "recorded_at < :until"),
            ("type", observation_type.value if observation_type else None, "type = :type"),
            ("source_type", source_type, "source_type = :source_type"),
            ("source_id", source_id, "id = :source_id"),
        ):
            if value is not None:
                clauses.append(clause)
                params[name] = value
        if source_types is not None:
            invalid_source_types = source_types - SOURCE_TYPES
            if invalid_source_types:
                raise ValueError(f"unknown clinical source types: {', '.join(sorted(invalid_source_types))}")
            if not source_types:
                return []
            clauses.append("source_type IN :source_types")
            params["source_types"] = sorted(source_types)
        query = f"SELECT * FROM ({CLINICAL_FEED_SQL}) feed WHERE {' AND '.join(clauses)}"
        query += " ORDER BY recorded_at DESC, source_type, id"
        if limit is not None:
            query += " LIMIT :limit OFFSET :offset"
            params.update(limit=limit, offset=offset)
        statement = text(query).bindparams(bindparam("resident_ids", expanding=True))
        if source_types is not None:
            statement = statement.bindparams(bindparam("source_types", expanding=True))
        rows = (await self._session.execute(statement, params)).mappings().all()
        result = []
        for row in rows:
            item = ObservationRead.model_validate(dict(row))
            item.is_implausible = item.is_implausible or not is_plausible(item.type, item.value)
            result.append(item)
        return result

    async def get_recent_for_resident(self, resident_id: uuid.UUID, hours: int = 24) -> list[ObservationSummary]:
        return (await self.get_recent_for_residents([resident_id], hours)).get(resident_id, [])

    async def get_recent_for_residents(
        self,
        resident_ids: list[uuid.UUID],
        hours: int = 24,
    ) -> dict[uuid.UUID, list[ObservationSummary]]:
        now = datetime.now(UTC)
        rows = await self._read(resident_ids, since=now - timedelta(hours=hours), until=now)
        by_resident: dict[uuid.UUID, list[ObservationSummary]] = defaultdict(list)
        for row in rows:
            by_resident[row.resident_id].append(ObservationSummary.model_validate(row.model_dump()))
        return dict(by_resident)

    async def create(self, observation: Observation) -> Observation:
        resident = await self._session.scalar(
            text("SELECT id FROM residents WHERE id=:id AND care_home_id=:home AND deleted_at IS NULL"),
            {"id": observation.resident_id, "home": observation.care_home_id},
        )
        if resident is None:
            raise NotFoundError("resident not found")
        # Preserve transaction usability and let the constraint catch racing retries.
        try:
            async with self._session.begin_nested():
                self._session.add(observation)
                await self._session.flush()
        except IntegrityError as exc:
            if observation.idempotency_key is not None:
                existing = await self._session.scalar(
                    select(Observation).where(
                        Observation.care_home_id == observation.care_home_id,
                        Observation.idempotency_key == observation.idempotency_key,
                    )
                )
                if existing is not None:
                    raise ConflictError("observation idempotency key already exists") from exc
            raise
        return observation

    async def list_for_resident(
        self,
        resident_id: uuid.UUID,
        limit: int = 100,
        *,
        offset: int = 0,
        since: datetime | None = None,
        until: datetime | None = None,
        observation_type: ObservationType | None = None,
    ) -> list[ObservationRead]:
        return await self._read(
            [resident_id],
            limit=limit,
            offset=offset,
            since=since,
            until=until,
            observation_type=observation_type,
        )

    async def list_clinical_evidence_for_resident(
        self,
        resident_id: uuid.UUID,
        *,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        source_types: set[str] | None = None,
        source_id: uuid.UUID | None = None,
        limit: int = 100,
    ) -> list[ObservationRead]:
        """Read the normalised clinical-history projection for resident search.

        The caller supplies the same RLS-scoped session used by all observation
        reads.  This is deliberately a projection reader, not a new endpoint or
        a duplicate per-table search implementation.
        """
        return await self._read(
            [resident_id],
            since=from_date,
            until=to_date,
            source_types=source_types,
            source_id=source_id,
            limit=limit,
        )

    async def get_source(
        self,
        resident_id: uuid.UUID,
        source_type: str,
        source_id: uuid.UUID,
    ) -> ObservationRead | None:
        if source_type not in SOURCE_TYPES:
            return None
        rows = await self._read([resident_id], source_type=source_type, source_id=source_id)
        return rows[0] if rows else None
