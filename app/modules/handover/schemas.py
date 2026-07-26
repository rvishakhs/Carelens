from pydantic import BaseModel

from app.modules.observations.schemas import ObservationSummary
from app.modules.residents.schemas import ResidentSummary
from app.modules.summaries.schemas import SummaryRead


class HandoverResidentCard(BaseModel):
    resident: ResidentSummary
    latest_summary: SummaryRead | None
    recent_observations: list[ObservationSummary]
