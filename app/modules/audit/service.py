import uuid

from app.modules.audit.models import AuditEvent
from app.modules.audit.repository import AuditRepository


class AuditService:
    """Explicit-call API for actions that aren't already domain events -- e.g. views
    and exports. `handover` calls this directly for RecordViewed-style entries that
    don't warrant a full DomainEvent subclass; everything else flows in via
    module.py's event subscriptions."""

    def __init__(self, repository: AuditRepository):
        self._repository = repository

    async def log(
        self,
        *,
        care_home_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None = None,
        justification: str | None = None,
        metadata: dict | None = None,
    ) -> AuditEvent:
        entry = AuditEvent(
            care_home_id=care_home_id,
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            justification=justification,
            event_metadata=metadata or {},
        )
        return await self._repository.append(entry)
