import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.floors.models import Floor, UserFloorLink
from app.modules.floors.ports import FloorReader


class FloorRepository(FloorReader):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_authorized_floor_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        result = await self._session.execute(
            select(UserFloorLink.floor_id).where(
                UserFloorLink.user_id == user_id,
                UserFloorLink.revoked_at.is_(None),
                UserFloorLink.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def list_active(self) -> list[Floor]:
        result = await self._session.execute(select(Floor).where(Floor.is_active, Floor.deleted_at.is_(None)))
        return list(result.scalars().all())

    async def create(self, floor: Floor) -> Floor:
        self._session.add(floor)
        await self._session.flush()
        return floor

    async def grant_access(
        self, care_home_id: uuid.UUID, user_id: uuid.UUID, floor_id: uuid.UUID, granted_by: uuid.UUID
    ) -> UserFloorLink:
        link = UserFloorLink(
            care_home_id=care_home_id,
            user_id=user_id,
            floor_id=floor_id,
            granted_by=granted_by,
            granted_at=datetime.now(UTC),
        )
        self._session.add(link)
        await self._session.flush()
        return link

    async def revoke_access(self, user_id: uuid.UUID, floor_id: uuid.UUID) -> None:
        result = await self._session.execute(
            select(UserFloorLink).where(
                UserFloorLink.user_id == user_id,
                UserFloorLink.floor_id == floor_id,
                UserFloorLink.revoked_at.is_(None),
            )
        )
        link = result.scalar_one_or_none()
        if link is not None:
            link.revoked_at = datetime.now(UTC)
            await self._session.flush()
