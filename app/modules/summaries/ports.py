"""Public read interface -- `handover` imports SummaryReader from here, never
summaries.repository or summaries.models."""

import abc
import uuid

from app.modules.summaries.schemas import SummaryRead


class SummaryReader(abc.ABC):
    @abc.abstractmethod
    async def get_latest_for_resident(self, resident_id: uuid.UUID) -> SummaryRead | None: ...

    @abc.abstractmethod
    async def get_latest_for_residents(self, resident_ids: list[uuid.UUID]) -> dict[uuid.UUID, SummaryRead]:
        """Bulk variant -- the handover read-model uses this instead of N calls to
        get_latest_for_resident() to stay at one query for the whole grid."""
        ...
