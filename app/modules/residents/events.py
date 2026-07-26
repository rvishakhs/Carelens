import uuid

from app.shared.events import DomainEvent


class ResidentCreated(DomainEvent):
    resident_id: uuid.UUID
