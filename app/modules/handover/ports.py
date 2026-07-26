"""Public interface for ordering the handover grid. Phase 1's default implementation
(adapters/recency_ranker.py) ranks by recency of incident/refusal mentions in notes;
Phase 2 swaps in the real change-detection rules engine without handover.service.py
changing -- see governance/decision-log.md.

handover itself exposes no reader port -- it is a terminal read-model, like audit,
that nothing else in the app depends on."""

import abc
import uuid

from app.modules.observations.schemas import ObservationSummary


class AttentionRanker(abc.ABC):
    @abc.abstractmethod
    def score(self, resident_id: uuid.UUID, recent_observations: list[ObservationSummary]) -> float:
        """Higher score = needs attention sooner."""
        ...
