import uuid

from app.modules.ai_insights.events import AIAlertAcknowledged
from app.modules.ai_insights.models import ResidentAIAlert, ResidentAISummary
from app.modules.ai_insights.repository import AIInsightRepository
from app.modules.ai_insights.schemas import AlertAcknowledgeRequest, SummaryFeedbackCreate
from app.shared.events import EventBus
from app.shared.exceptions import NotFoundError


class AIInsightService:
    def __init__(self, repository: AIInsightRepository, event_bus: EventBus):
        self._repository = repository
        self._event_bus = event_bus

    async def submit_summary_feedback(
        self, care_home_id: uuid.UUID, actor_user_id: uuid.UUID, summary_id: uuid.UUID, feedback: SummaryFeedbackCreate
    ) -> ResidentAISummary:
        summary = await self._repository.get_summary_by_id(summary_id)
        if summary is None:
            raise NotFoundError(f"summary {summary_id} not found")
        summary.feedback_rating = feedback.rating
        summary.feedback_comment = feedback.comment
        summary.feedback_by = actor_user_id
        return await self._repository.save_summary(summary)

    async def acknowledge_alert(
        self, care_home_id: uuid.UUID, actor_user_id: uuid.UUID, alert_id: uuid.UUID, data: AlertAcknowledgeRequest
    ) -> ResidentAIAlert:
        alert = await self._repository.get_alert_by_id(alert_id)
        if alert is None:
            raise NotFoundError(f"alert {alert_id} not found")

        alert = await self._repository.acknowledge_alert(alert, actor_user_id, data.resolution_note)

        await self._event_bus.publish(
            AIAlertAcknowledged(
                care_home_id=care_home_id, actor_user_id=actor_user_id, alert_id=alert.id, resident_id=alert.resident_id
            )
        )
        return alert
