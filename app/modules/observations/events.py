import uuid

from app import DomainEvent, ObservationType


class ObservationRecorded(DomainEvent):
    observation_id: uuid.UUID
    resident_id: uuid.UUID
    type: ObservationType
    is_implausible: bool
