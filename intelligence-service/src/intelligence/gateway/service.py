from typing import Literal

from intelligence.core.contracts import Claim, EvidenceBundle, SourceRef
from intelligence.core.errors import GatewayRejected
from intelligence.gateway.contracts import Provider, SafePayload


class Gateway:
    """Synthetic structured boundary. NOT a free-text pseudonymiser for real residents."""

    def __init__(self, provider: Provider) -> None:
        self._provider = provider

    async def summarise(
        self, bundle: EvidenceBundle, intent: Literal["history", "handover"]
    ) -> tuple[Claim, ...]:
        if any(record.kind != "fluid" for record in bundle.records):
            raise GatewayRejected
        aliases = {f"SOURCE_{i}": row.reference for i, row in enumerate(bundle.records, 1)}
        consumed = [r.consumed_ml for r in bundle.records]
        offered = [r.offered_ml for r in bundle.records]
        totals = {
            "consumed_ml": sum(v for v in consumed if v is not None)
            if consumed and all(v is not None for v in consumed)
            else None,
            "offered_ml": sum(v for v in offered if v is not None)
            if offered and all(v is not None for v in offered)
            else None,
            "no_records": None,
        }
        payload = SafePayload(
            intent=intent,
            source_aliases=tuple(aliases),
            consumed_ml=totals["consumed_ml"],
            offered_ml=totals["offered_ml"],
        )
        output = await self._provider.generate(payload)
        expected = {"consumed_ml", "offered_ml"} if aliases else {"no_records"}
        if len(output.claims) != len(expected) or {c.metric for c in output.claims} != expected:
            raise GatewayRejected
        claims = []
        for claim in output.claims:
            if (
                claim.resident_alias != payload.resident_alias
                or set(claim.source_aliases) != set(aliases)
                or len(claim.source_aliases) != len(aliases)
                or claim.value != totals[claim.metric]
            ):
                raise GatewayRejected
            refs: tuple[SourceRef, ...] = tuple(aliases[a] for a in claim.source_aliases)
            if claim.metric == "no_records":
                text = "No records found in this synthetic fixture period; this does not mean zero intake."
            else:
                label = "consumed" if claim.metric == "consumed_ml" else "offered"
                text = (
                    f"Recorded {label}: {claim.value} ml."
                    if claim.value is not None
                    else f"Total {label} is not fully recorded."
                )
            claims.append(Claim(text=text, sources=refs))
        # aliases are local to this call and never persisted or exposed to the provider as a map.
        return tuple(claims)
