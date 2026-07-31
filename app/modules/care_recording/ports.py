"""Public read interface -- other modules (ai_insights, handover) import
CareEventReader from here and get_care_event_reader from dependencies.py, never
care_recording.repository or care_recording.models directly."""

import abc
import uuid

from app.modules.care_recording.schemas import CareEventRead


class CareEventReader(abc.ABC):
    @abc.abstractmethod
    async def get_recent_for_resident(self, resident_id: uuid.UUID, hours: int = 24) -> list[CareEventRead]: ...
