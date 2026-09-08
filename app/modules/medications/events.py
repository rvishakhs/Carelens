import uuid

from app import MedicationEventStatus
from app import DomainEvent


class MedicationEventRecorded(DomainEvent):
    """Not yet in audit/module.py's subscription list -- wire it up there when this
    module is first enabled in ENABLED_MODULES."""

    medication_event_id: uuid.UUID
    resident_id: uuid.UUID
    status: MedicationEventStatus
