"""Deterministic test provider. No network, credentials or inferred narrative."""

from intelligence.gateway.contracts import MAX_CLAIMS, HandoverClaim, HandoverOutput, HandoverPayload
from intelligence.gateway.validation import (
    GatewayValidationError,
    evidence_claim_text,
    metric_claim_text,
    validate_outbound_payload,
)


class FakeHandoverProvider:
    async def generate(self, payload: HandoverPayload) -> HandoverOutput:
        validate_outbound_payload(payload)
        claims = [
            HandoverClaim(
                section=e.category,
                context=e.context,
                text=evidence_claim_text(e),
                source_aliases=(e.source_alias,),
            )
            for e in payload.evidence
        ]
        claims.extend(
            HandoverClaim(
                section=m.category,
                context=m.context,
                text=metric_claim_text(m),
                source_aliases=m.source_aliases,
                metric_aliases=(m.metric_alias,),
            )
            for m in payload.metrics
            if m.source_aliases
        )
        if len(claims) > MAX_CLAIMS:
            raise GatewayValidationError("Fake provider output exceeds claim budget")
        return HandoverOutput(resident_alias=payload.resident_alias, claims=tuple(claims))
