import uuid

from app import DomainEvent


class ResidentCreated(DomainEvent):
    resident_id: uuid.UUID
