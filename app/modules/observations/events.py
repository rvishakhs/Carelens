import uuid

from app import ObservationType
from app import DomainEvent


class ObservationRecorded(DomainEvent):
    observation_id: uuid.UUID
    resident_id: uuid.UUID
    type: ObservationType
    is_implausible: bool
