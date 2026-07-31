"""Public read interface -- `handover` imports AIInsightReader from here and
get_ai_insight_reader from dependencies.py, never ai_insights.repository directly."""

import abc
import uuid

from app.modules.ai_insights.schemas import ResidentAIAlertRead, ResidentAISummaryRead


class AIInsightReader(abc.ABC):
    @abc.abstractmethod
    async def get_latest_summary(self, resident_id: uuid.UUID) -> ResidentAISummaryRead | None: ...

    @abc.abstractmethod
    async def get_open_alerts(self, resident_id: uuid.UUID) -> list[ResidentAIAlertRead]: ...
