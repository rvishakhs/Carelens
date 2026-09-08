from pydantic import BaseModel

from app import ObservationSummary
from app import ResidentSummary
from app import SummaryRead


class HandoverResidentCard(BaseModel):
    resident: ResidentSummary
    latest_summary: SummaryRead | None
    recent_observations: list[ObservationSummary]
