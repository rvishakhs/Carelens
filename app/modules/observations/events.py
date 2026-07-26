import uuid

from app.modules.observations.models import ObservationType
from app.shared.events import DomainEvent


class ObservationRecorded(DomainEvent):
    observation_id: uuid.UUID
    resident_id: uuid.UUID
    type: ObservationType
    is_implausible: bool
