"""Observation retrieval and assembly; not proof of complete handover coverage."""

from uuid import UUID

from pydantic import SecretStr

from intelligence.connectors.carelens import CareLensClient
from intelligence.connectors.normalise import normalise_observation
from intelligence.connectors.windows import observation_fetch_period
from intelligence.core.contracts import ExecutionContext, Period
from intelligence.handover.evidence import (
    EvidenceValidationError,
    ShiftEvidence,
    assemble_shift_evidence,
)


async def retrieve_shift_observations(
    client: CareLensClient,
    *,
    context: ExecutionContext,
    resident_id: UUID,
    access_token: SecretStr,
    shift: Period,
    care_home_timezone: str,
    page_size: int = 100,
    max_pages: int = 100,
) -> ShiftEvidence:
    """Use trusted execution scope and credentials, revalidated by the caller.

    Both clinical observations and care events are retrieved; snapshot consistency is not guaranteed.
    Transport/normalization failures propagate; no partial result is returned.
    """
    if resident_id not in context.authorised_resident_ids:
        raise EvidenceValidationError("Resident is outside the authorised scope")
    fetch = observation_fetch_period(shift, care_home_timezone=care_home_timezone)
    rows = await client.list_observations(
        resident_id,
        access_token,
        since=fetch.start,
        until=fetch.end,
        page_size=page_size,
        max_pages=max_pages,
    )
    rows += await client.list_care_events(
        resident_id, access_token, since=shift.start, until=shift.end,
        page_size=page_size, max_pages=max_pages,
    )
    records = []
    for row in rows:
        evidence = normalise_observation(row, context=context, expected_resident_id=resident_id)
        if evidence is not None:
            records.append(evidence)
    return assemble_shift_evidence(
        tuple(records),
        context=context,
        expected_resident_id=resident_id,
        period=shift,
        care_home_timezone=care_home_timezone,
    )
