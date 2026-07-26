import uuid

from app.shared.events import DomainEvent


class SummaryGenerated(DomainEvent):
    summary_id: uuid.UUID
    resident_id: uuid.UUID


class SummaryReviewed(DomainEvent):
    summary_id: uuid.UUID
    resident_id: uuid.UUID
    rating: str
