import uuid
from datetime import datetime
from typing import Protocol

from app.modules.resident_search.evidence.models import EvidenceDocument, EvidenceSourceType


class EvidenceSourceAdapter(Protocol):
    source_type: EvidenceSourceType

    async def find(
        self,
        *,
        resident_id: uuid.UUID,
        from_date: datetime | None,
        to_date: datetime | None,
        limit: int,
        topics: set[str] | None = None,
        statuses: set[str] | None = None,
        current_only: bool = False,
    ) -> list[EvidenceDocument]:
        """Return the current authorised source document, or None."""

    async def get(
        self,
        *,
        resident_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> EvidenceDocument | None:
        """Return the current authorised source document, or None."""
