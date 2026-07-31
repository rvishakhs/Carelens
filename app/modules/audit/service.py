import uuid

from app.modules.audit.models import AuditAction, AuditEvent
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
        actor_id: uuid.UUID | None,
        action: AuditAction,
        entity_type: str,
        entity_id: uuid.UUID | None = None,
        justification: str | None = None,
        ip_address: str | None = None,
        device_info: str | None = None,
    ) -> AuditEvent:
        entry = AuditEvent(
            care_home_id=care_home_id,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            justification=justification,
            ip_address=ip_address,
            device_info=device_info,
        )
        return await self._repository.append(entry)
