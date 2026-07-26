import uuid

from app.shared.events import DomainEvent


class RecordViewed(DomainEvent):
    """Fired once per resident rendered in a handover view. audit subscribes to this --
    it's the control most competitors lack: every read, not just every write, is
    logged."""

    resident_id: uuid.UUID
