"""Public read interface for other modules -- `handover` may show "meds due" when this
module is enabled. Since medications is flag-gated off by default (see
ENABLED_MODULES), consuming code must treat a missing MedicationReader as "feature
off" rather than assume its presence."""

import abc
import uuid

from app.modules.medications.schemas import MedicationRead


class MedicationReader(abc.ABC):
    @abc.abstractmethod
    async def list_for_resident(self, resident_id: uuid.UUID) -> list[MedicationRead]: ...
