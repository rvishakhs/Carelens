"""Resolve a persisted citation back to its current authorised source record."""

import uuid
from collections.abc import Mapping

from app.modules.resident_search.evidence.models import EvidenceDocument, EvidenceSourceType
from app.modules.resident_search.evidence.ports import EvidenceSourceAdapter


_ASSESSMENT_SOURCE_TYPES = frozenset({
    EvidenceSourceType.MOBILITY_ASSESSMENT,
    EvidenceSourceType.NUTRITION_ASSESSMENT,
    EvidenceSourceType.SKIN_ASSESSMENT,
    EvidenceSourceType.MENTAL_HEALTH_ASSESSMENT,
})


class EvidenceSourceResolver:
    """Single citation-resolution boundary used by resident search.

    The resolver never bypasses adapter/RLS checks.  Concrete assessment types
    are routed through their grouped adapter because the parent record's source
    type, rather than the group, is what is persisted in a citation.
    """

    def __init__(self, adapters: Mapping[EvidenceSourceType, EvidenceSourceAdapter]):
        self._adapters = dict(adapters)

    def adapter_group_for(self, source_type: EvidenceSourceType) -> EvidenceSourceType:
        return EvidenceSourceType.ASSESSMENT if source_type in _ASSESSMENT_SOURCE_TYPES else source_type

    async def resolve(
        self,
        *,
        resident_id: uuid.UUID,
        source_type: EvidenceSourceType,
        source_id: uuid.UUID,
    ) -> EvidenceDocument | None:
        adapter = self._adapters.get(self.adapter_group_for(source_type))
        if adapter is None:
            return None
        if source_type in _ASSESSMENT_SOURCE_TYPES:
            return await adapter.get(resident_id=resident_id, source_type=source_type, source_id=source_id)  # type: ignore[call-arg]
        return await adapter.get(resident_id=resident_id, source_id=source_id)
