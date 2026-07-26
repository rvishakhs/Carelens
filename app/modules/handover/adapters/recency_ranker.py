"""Phase 1 default AttentionRanker: recency-weighted count of refusal/fall mentions
pulled from notes' rule-based structured fields (observations.adapters.rule_based_structurer).
Deliberately crude -- Phase 2 replaces this with the real change-detection engine."""

import uuid
from datetime import UTC, datetime

from app.modules.handover.ports import AttentionRanker
from app.modules.observations.schemas import ObservationSummary

_MIN_HOURS_AGO = 0.1


class RecencyAttentionRanker(AttentionRanker):
    def score(self, resident_id: uuid.UUID, recent_observations: list[ObservationSummary]) -> float:
        now = datetime.now(UTC)
        score = 0.0
        for obs in recent_observations:
            structured = obs.value.get("structured") if isinstance(obs.value, dict) else None
            if not structured or not (structured.get("refusal_mentioned") or structured.get("fall_mentioned")):
                continue
            hours_ago = max((now - obs.recorded_at).total_seconds() / 3600, _MIN_HOURS_AGO)
            score += 10 / hours_ago
        return score
