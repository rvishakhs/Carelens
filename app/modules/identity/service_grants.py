"""Explicit, deny-by-default pilot service registrations; no implicit staff role."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IntelligenceServiceGrant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    client_id: str = Field(min_length=1)
    subject: UUID
    service_identity: str = Field(min_length=1)
    tenant_id: UUID
    floor_ids: frozenset[UUID]
    resident_ids: frozenset[UUID]
    # Explicit pilot enrolment, not inferred from the existence of a resident.
    eligible_resident_ids: frozenset[UUID] = frozenset()
    generating_staff_ids: frozenset[UUID] = frozenset()
    permissions: frozenset[Literal["handover:generate", "handover:schedule"]] = frozenset()
