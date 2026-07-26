"""Composes ResidentReader + ObservationReader + SummaryReader into the single
read-model the handover grid needs, using each reader's bulk method to stay at three
queries total for the whole grid (never N+1 per resident) -- see the <500ms/40-resident
target in the production checklist.

Every resident rendered here fires RecordViewed, which audit subscribes to."""

import uuid

from app.modules.handover.events import RecordViewed
from app.modules.handover.ports import AttentionRanker
from app.modules.handover.schemas import HandoverResidentCard
from app.modules.observations.ports import ObservationReader
from app.modules.residents.ports import ResidentReader
from app.modules.summaries.ports import SummaryReader
from app.shared.events import EventBus


class HandoverService:
    def __init__(
        self,
        resident_reader: ResidentReader,
        observation_reader: ObservationReader,
        summary_reader: SummaryReader,
        attention_ranker: AttentionRanker,
        event_bus: EventBus,
    ):
        self._resident_reader = resident_reader
        self._observation_reader = observation_reader
        self._summary_reader = summary_reader
        self._attention_ranker = attention_ranker
        self._event_bus = event_bus

    async def get_handover_view(self, care_home_id: uuid.UUID, actor_user_id: uuid.UUID) -> list[HandoverResidentCard]:
        residents = await self._resident_reader.list_active_residents()
        resident_ids = [r.id for r in residents]

        observations_by_resident = await self._observation_reader.get_recent_for_residents(resident_ids, hours=24)
        summaries_by_resident = await self._summary_reader.get_latest_for_residents(resident_ids)

        scored: list[tuple[float, HandoverResidentCard]] = []
        for resident in residents:
            recent_observations = observations_by_resident.get(resident.id, [])
            card = HandoverResidentCard(
                resident=resident,
                latest_summary=summaries_by_resident.get(resident.id),
                recent_observations=recent_observations,
            )
            score = self._attention_ranker.score(resident.id, recent_observations)
            scored.append((score, card))

            await self._event_bus.publish(
                RecordViewed(care_home_id=care_home_id, actor_user_id=actor_user_id, resident_id=resident.id)
            )

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [card for _, card in scored]
