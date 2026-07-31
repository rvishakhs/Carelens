import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_insights.models import ResidentAIAlert, ResidentAIReport, ResidentAISummary, ResidentPrediction
from app.modules.ai_insights.ports import AIInsightReader
from app.modules.ai_insights.schemas import ResidentAIAlertRead, ResidentAISummaryRead


class AIInsightRepository(AIInsightReader):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_latest_summary(self, resident_id: uuid.UUID) -> ResidentAISummaryRead | None:
        result = await self._session.execute(
            select(ResidentAISummary)
            .where(
                ResidentAISummary.resident_id == resident_id,
                ResidentAISummary.is_current,
                ResidentAISummary.deleted_at.is_(None),
            )
            .order_by(ResidentAISummary.generated_at.desc())
            .limit(1)
        )
        summary = result.scalar_one_or_none()
        return ResidentAISummaryRead.model_validate(summary) if summary else None

    async def get_open_alerts(self, resident_id: uuid.UUID) -> list[ResidentAIAlertRead]:
        result = await self._session.execute(
            select(ResidentAIAlert)
            .where(
                ResidentAIAlert.resident_id == resident_id,
                ResidentAIAlert.status == "open",
                ResidentAIAlert.deleted_at.is_(None),
            )
            .order_by(ResidentAIAlert.generated_at.desc())
        )
        return [ResidentAIAlertRead.model_validate(a) for a in result.scalars().all()]

    async def list_summaries(self, resident_id: uuid.UUID, limit: int = 30) -> list[ResidentAISummary]:
        result = await self._session.execute(
            select(ResidentAISummary)
            .where(ResidentAISummary.resident_id == resident_id, ResidentAISummary.deleted_at.is_(None))
            .order_by(ResidentAISummary.generated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_reports(self, resident_id: uuid.UUID, limit: int = 30) -> list[ResidentAIReport]:
        result = await self._session.execute(
            select(ResidentAIReport)
            .where(ResidentAIReport.resident_id == resident_id, ResidentAIReport.deleted_at.is_(None))
            .order_by(ResidentAIReport.generated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_alerts(self, resident_id: uuid.UUID, limit: int = 30) -> list[ResidentAIAlert]:
        result = await self._session.execute(
            select(ResidentAIAlert)
            .where(ResidentAIAlert.resident_id == resident_id, ResidentAIAlert.deleted_at.is_(None))
            .order_by(ResidentAIAlert.generated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_predictions(self, resident_id: uuid.UUID, limit: int = 30) -> list[ResidentPrediction]:
        result = await self._session.execute(
            select(ResidentPrediction)
            .where(ResidentPrediction.resident_id == resident_id, ResidentPrediction.deleted_at.is_(None))
            .order_by(ResidentPrediction.generated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_summary_by_id(self, summary_id: uuid.UUID) -> ResidentAISummary | None:
        return await self._session.get(ResidentAISummary, summary_id)

    async def get_alert_by_id(self, alert_id: uuid.UUID) -> ResidentAIAlert | None:
        return await self._session.get(ResidentAIAlert, alert_id)

    async def save_summary(self, summary: ResidentAISummary) -> ResidentAISummary:
        await self._session.flush()
        return summary

    async def acknowledge_alert(
        self, alert: ResidentAIAlert, acknowledged_by: uuid.UUID, resolution_note: str | None
    ) -> ResidentAIAlert:
        alert.status = "acknowledged"
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.now(UTC)
        alert.resolution_note = resolution_note
        await self._session.flush()
        return alert
