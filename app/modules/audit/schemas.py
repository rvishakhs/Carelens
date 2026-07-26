import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditEventRead(BaseModel):
    id: uuid.UUID
    created_at: datetime
    actor_user_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    justification: str | None
    event_metadata: dict

    model_config = {"from_attributes": True}
