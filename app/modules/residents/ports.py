"""Public read interface other modules depend on. `summaries` and `handover` may call
ResidentReader; they must never import residents.repository or residents.models."""

import abc
import uuid

from app.modules.residents.schemas import ResidentSummary


class ResidentReader(abc.ABC):
    @abc.abstractmethod
    async def get_resident(self, resident_id: uuid.UUID) -> ResidentSummary | None: ...

    @abc.abstractmethod
    async def list_active_residents(self) -> list[ResidentSummary]: ...