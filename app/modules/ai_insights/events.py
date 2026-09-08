import uuid

from app import DomainEvent


class AIAlertRaised(DomainEvent):
    alert_id: uuid.UUID
    resident_id: uuid.UUID
    severity: str


class AIAlertAcknowledged(DomainEvent):
    alert_id: uuid.UUID
    resident_id: uuid.UUID
