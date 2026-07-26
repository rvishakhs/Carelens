"""Public interfaces other modules depend on -- summaries/handover import these, never
observations.repository or observations.models."""

import abc
import uuid

from app.modules.observations.schemas import ObservationSummary


class ObservationReader(abc.ABC):
    @abc.abstractmethod
    async def get_recent_for_resident(self, resident_id: uuid.UUID, hours: int = 24) -> list[ObservationSummary]: ...

    @abc.abstractmethod
    async def get_recent_for_residents(
        self, resident_ids: list[uuid.UUID], hours: int = 24
    ) -> dict[uuid.UUID, list[ObservationSummary]]:
        """Bulk variant -- the handover read-model uses this instead of N calls to
        get_recent_for_resident() to stay at one query for the whole grid."""
        ...


class NoteStructurer(abc.ABC):
    """Extracts structured fields (e.g. mood, appetite, incident flags) from free-text
    notes. Phase 1 ships a rule-based adapter; an LLM-backed adapter arrives later
    without this interface changing -- see adapters/rule_based_structurer.py."""

    @abc.abstractmethod
    async def structure(self, text: str) -> dict: ...
