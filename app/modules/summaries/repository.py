import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.summaries.models import AIOutput
from app.modules.summaries.ports import SummaryReader
from app.modules.summaries.schemas import SummaryRead


class SummaryRepository(SummaryReader):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_latest_for_resident(self, resident_id: uuid.UUID) -> SummaryRead | None:
        result = await self._session.execute(
            select(AIOutput)
            .where(AIOutput.resident_id == resident_id, AIOutput.deleted_at.is_(None))
            .order_by(AIOutput.generated_at.desc())
            .limit(1)
        )
        output = result.scalar_one_or_none()
        return SummaryRead.model_validate(output) if output else None

    async def get_latest_for_residents(self, resident_ids: list[uuid.UUID]) -> dict[uuid.UUID, SummaryRead]:
        if not resident_ids:
            return {}
        # DISTINCT ON is Postgres-specific -- fine per the stack's fixed choice of PG16.
        stmt = (
            select(AIOutput)
            .distinct(AIOutput.resident_id)
            .where(AIOutput.resident_id.in_(resident_ids), AIOutput.deleted_at.is_(None))
            .order_by(AIOutput.resident_id, AIOutput.generated_at.desc())
        )
        result = await self._session.execute(stmt)
        return {o.resident_id: SummaryRead.model_validate(o) for o in result.scalars().all()}

    async def create(self, output: AIOutput) -> AIOutput:
        self._session.add(output)
        await self._session.flush()
        return output

    async def get_by_id(self, summary_id: uuid.UUID) -> AIOutput | None:
        return await self._session.get(AIOutput, summary_id)

    async def save(self, output: AIOutput) -> AIOutput:
        await self._session.flush()
        return output
