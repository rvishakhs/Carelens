import uuid

from app import DomainEvent


class ResidentHistorySearched(DomainEvent):
    """Metadata-only search audit event.

    The search phrase and returned clinical text must never travel on the event bus:
    audit handlers are deliberately able to persist event metadata.  A count is
    sufficient for operational monitoring without creating another sensitive copy of
    a resident's history or the staff member's question.
    """

    resident_id: uuid.UUID
    result_count: int
