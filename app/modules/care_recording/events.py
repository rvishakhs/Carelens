import uuid

from app.shared.events import DomainEvent


class CareEventRecorded(DomainEvent):
    care_event_id: uuid.UUID
    resident_id: uuid.UUID
    template_id: uuid.UUID
    status: str
