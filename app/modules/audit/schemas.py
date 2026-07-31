import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.audit.models import AuditAction


class AuditEventRead(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    actor_id: uuid.UUID | None
    action: AuditAction
    entity_type: str
    entity_id: uuid.UUID | None
    justification: str | None

    model_config = {"from_attributes": True}
