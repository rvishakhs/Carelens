import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.residents.models import Resident, ResidentStatus
from app.modules.residents.ports import ResidentReader
from app.modules.residents.schemas import ResidentSummary


class ResidentRepository(ResidentReader):
    """Implements the public ResidentReader port alongside full CRUD. Other modules
    should only ever hold a `ResidentReader`-typed reference to this class, obtained
    via residents.dependencies.get_resident_reader -- never construct it directly."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_resident(self, resident_id: uuid.UUID) -> ResidentSummary | None:
        resident = await self._session.get(Resident, resident_id)
        if resident is None or resident.deleted_at is not None:
            return None
        return ResidentSummary(
            id=resident.id,
            display_name=f"{resident.first_name} {resident.last_name}",
            room=resident.room,
            status=resident.status,
        )

    async def list_active_residents(self) -> list[ResidentSummary]:
        result = await self._session.execute(
            select(Resident).where(Resident.status == ResidentStatus.ACTIVE, Resident.deleted_at.is_(None))
        )
        return [
            ResidentSummary(id=r.id, display_name=f"{r.first_name} {r.last_name}", room=r.room, status=r.status)
            for r in result.scalars().all()
        ]

    async def list_active(self) -> list[Resident]:
        """Full-record listing for residents' own router -- distinct from the
        ResidentReader.list_active_residents() summary used cross-module."""
        result = await self._session.execute(
            select(Resident).where(Resident.status == ResidentStatus.ACTIVE, Resident.deleted_at.is_(None))
        )
        return list(result.scalars().all())

    async def create(self, resident: Resident) -> Resident:
        self._session.add(resident)
        await self._session.flush()
        return resident

    async def get_by_id(self, resident_id: uuid.UUID) -> Resident | None:
        return await self._session.get(Resident, resident_id)
