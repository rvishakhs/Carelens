from typing import Protocol
from uuid import UUID

from intelligence.core.contracts import EvidenceBundle, Period, Scope


class EvidenceReader(Protocol):
    async def retrieve(self, scope: Scope, resident_id: UUID, period: Period) -> EvidenceBundle: ...
