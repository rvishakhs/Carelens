import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditEvent


class AuditRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def append(self, entry: AuditEvent) -> AuditEvent:
        """INSERT only -- there is no update()/delete() on this repository by design."""
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def list_events(
        self,
        *,
        entity_type: str | None = None,
        actor_id: uuid.UUID | None = None,
        since: datetime | None = None,
        limit: int = 200,
    ) -> list[AuditEvent]:
        stmt = select(AuditEvent).order_by(AuditEvent.occurred_at.desc()).limit(limit)
        if entity_type is not None:
            stmt = stmt.where(AuditEvent.entity_type == entity_type)
        if actor_id is not None:
            stmt = stmt.where(AuditEvent.actor_id == actor_id)
        if since is not None:
            stmt = stmt.where(AuditEvent.occurred_at >= since)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
