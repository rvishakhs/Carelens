"""Generates and stores daily summaries via ai_gateway, with full input-record
provenance. Failures degrade gracefully: if generate_daily_summary raises, the worker
job (workers/jobs/summary_job.py) catches it per-resident and moves on -- no AIOutput
row is written, so the handover view falls back to raw structured data instead of
blocking care."""

import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.modules.ai_gateway.service import AIGatewayService
from app.modules.observations.models import ObservationType
from app.modules.observations.ports import ObservationReader
from app.modules.observations.schemas import ObservationSummary
from app.modules.residents.ports import ResidentReader
from app.modules.summaries.events import SummaryGenerated, SummaryReviewed
from app.modules.summaries.models import AIOutput
from app.modules.summaries.repository import SummaryRepository
from app.modules.summaries.schemas import SummaryFeedbackCreate
from app.shared.events import EventBus
from app.shared.exceptions import NotFoundError

PROMPT_TEMPLATE_VERSION = "v1"
_PROMPT_DIR = Path(__file__).resolve().parent.parent / "ai_gateway" / "prompts" / "daily_summary"
_PROMPT_PATH = _PROMPT_DIR / f"{PROMPT_TEMPLATE_VERSION}.md"


class SummaryService:
    def __init__(
        self,
        repository: SummaryRepository,
        observation_reader: ObservationReader,
        resident_reader: ResidentReader,
        ai_gateway: AIGatewayService,
        event_bus: EventBus,
    ):
        self._repository = repository
        self._observation_reader = observation_reader
        self._resident_reader = resident_reader
        self._ai_gateway = ai_gateway
        self._event_bus = event_bus

    async def generate_daily_summary(self, care_home_id: uuid.UUID, resident_id: uuid.UUID) -> AIOutput:
        resident = await self._resident_reader.get_resident(resident_id)
        if resident is None:
            raise NotFoundError(f"resident {resident_id} not found")

        observations = await self._observation_reader.get_recent_for_resident(resident_id, hours=24)
        structured = [o for o in observations if o.type is not ObservationType.NOTE]
        notes = [o for o in observations if o.type is ObservationType.NOTE]

        prompt = self._render_prompt(structured, notes)
        content = await self._ai_gateway.complete(
            care_home_id=care_home_id,
            resident_id=resident_id,
            resident_display_name=resident.display_name,
            prompt=prompt,
        )

        output = AIOutput(
            care_home_id=care_home_id,
            resident_id=resident_id,
            task="daily_summary",
            prompt_template_version=PROMPT_TEMPLATE_VERSION,
            model_version="unknown",  # TODO: surface provider/model string from LLMProvider
            content=content,
            source_observation_ids=[o.id for o in observations],
            generated_at=datetime.now(UTC),
        )
        output = await self._repository.create(output)

        await self._event_bus.publish(
            SummaryGenerated(care_home_id=care_home_id, summary_id=output.id, resident_id=resident_id)
        )
        return output

    def _render_prompt(self, structured: list[ObservationSummary], notes: list[ObservationSummary]) -> str:
        template = _PROMPT_PATH.read_text()
        structured_text = "\n".join(f"- {o.type.value}: {o.value}" for o in structured) or "(none recorded)"
        notes_text = "\n".join(f"- {o.value.get('text', '')}" for o in notes) or "(none recorded)"
        return template.replace("{{structured_observations}}", structured_text).replace("{{notes}}", notes_text)

    async def submit_feedback(
        self,
        care_home_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        summary_id: uuid.UUID,
        feedback: SummaryFeedbackCreate,
    ) -> AIOutput:
        output = await self._repository.get_by_id(summary_id)
        if output is None:
            raise NotFoundError(f"summary {summary_id} not found")

        output.feedback_rating = feedback.rating
        output.feedback_comment = feedback.comment
        output.feedback_by = actor_user_id
        output = await self._repository.save(output)

        await self._event_bus.publish(
            SummaryReviewed(
                care_home_id=care_home_id,
                actor_user_id=actor_user_id,
                summary_id=output.id,
                resident_id=output.resident_id,
                rating=feedback.rating.value,
            )
        )
        return output
