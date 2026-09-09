from typing import Literal, Protocol

from pydantic import Field

from intelligence.core.contracts import Contract


class SafePayload(Contract):
    # No free text, source UUIDs, credentials or identity maps cross this demo boundary.
    resident_alias: str = "RESIDENT_A"
    intent: Literal["history", "handover"]
    source_aliases: tuple[str, ...]
    consumed_ml: int | None = Field(ge=0)
    offered_ml: int | None = Field(ge=0)


class ProviderClaim(Contract):
    resident_alias: str
    source_aliases: tuple[str, ...]
    metric: Literal["consumed_ml", "offered_ml", "no_records"]
    value: int | None


class ProviderOutput(Contract):
    claims: tuple[ProviderClaim, ...]


class Provider(Protocol):
    async def generate(self, payload: SafePayload) -> ProviderOutput: ...
