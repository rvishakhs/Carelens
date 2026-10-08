"""Structural and deterministic support checks at the provider boundary."""

from pydantic import ValidationError
from intelligence.handover.prose import evidence_prose, metric_prose

from .contracts import MAX_CLAIM_CHARACTERS, MAX_CLAIMS, HandoverOutput, HandoverPayload
from .privacy import PrivacyRejected, check_text

MAX_PAYLOAD_BYTES = 256_000
MAX_OUTPUT_BYTES = 64_000


class GatewayValidationError(ValueError):
    pass


class OutboundValidationError(GatewayValidationError):
    pass


class InboundValidationError(GatewayValidationError):
    pass


def validate_outbound_payload(payload: HandoverPayload) -> None:
    """Structural/size/pattern checks; caller must first apply the text policy."""
    try:
        # Revalidate nested objects too, including objects made with model_copy.
        data = payload.model_dump_json()
        HandoverPayload.model_validate_json(data)
        if len(data.encode()) > MAX_PAYLOAD_BYTES:
            raise OutboundValidationError("Outbound payload exceeds byte limit")
        check_text(data)
    except (ValidationError, PrivacyRejected, ValueError) as exc:
        if isinstance(exc, OutboundValidationError):
            raise
        raise OutboundValidationError("Outbound structure or privacy check failed") from None
    sources = {e.source_alias: e for e in payload.evidence}
    if len(sources) != len(payload.evidence):
        raise OutboundValidationError("Outbound payload contains duplicate source aliases")
    metrics = {m.metric_alias: m for m in payload.metrics}
    if len(metrics) != len(payload.metrics) or len({m.metric for m in payload.metrics}) != len(metrics):
        raise OutboundValidationError("Duplicate metric identity")
    if len(payload.evidence) + sum(bool(m.source_aliases) for m in payload.metrics) > MAX_CLAIMS:
        raise OutboundValidationError("Extractive output would exceed claim budget")
    if any(len(evidence_claim_text(e)) > MAX_CLAIM_CHARACTERS for e in payload.evidence):
        raise OutboundValidationError("Extractive evidence exceeds claim text budget")
    for metric in payload.metrics:
        if any(s not in sources for s in metric.source_aliases):
            raise OutboundValidationError("Metric references unavailable evidence")
        if any(
            sources[s].context != "shift" or sources[s].category != metric.category
            for s in metric.source_aliases
        ):
            raise OutboundValidationError("Metric references incompatible evidence")
        if not payload.coverage_complete and metric.status == "complete":
            raise OutboundValidationError("Complete metric conflicts with coverage")


def evidence_claim_text(evidence) -> str:
    return evidence_prose(evidence.time_label, evidence.content)


def metric_claim_text(metric) -> str:
    return metric_prose(metric.metric, metric.value, metric.known_subtotal, metric.status, metric.unit)


def validate_inbound_output(*, output: HandoverOutput, payload: HandoverPayload) -> None:
    try:
        data = output.model_dump_json()
        HandoverOutput.model_validate_json(data)
        if len(data.encode()) > MAX_OUTPUT_BYTES:
            raise InboundValidationError("Provider output exceeds byte limit")
        check_text(data)
    except (ValidationError, PrivacyRejected, ValueError) as exc:
        if isinstance(exc, InboundValidationError):
            raise
        raise InboundValidationError("Provider output structure or privacy check failed") from None
    if output.resident_alias != payload.resident_alias:
        raise InboundValidationError("Resident alias mismatch")
    sources = {e.source_alias: e for e in payload.evidence}
    metrics = {m.metric_alias: m for m in payload.metrics}
    seen = set()
    for claim in output.claims:
        if len(set(claim.source_aliases)) != len(claim.source_aliases) or len(
            set(claim.metric_aliases)
        ) != len(claim.metric_aliases):
            raise InboundValidationError("Duplicate claim references")
        if any(s not in sources for s in claim.source_aliases):
            raise InboundValidationError("Unknown source citation")
        if any(m not in metrics for m in claim.metric_aliases):
            raise InboundValidationError("Unknown metric citation")
        cited = [sources[s] for s in claim.source_aliases]
        contexts = {e.context for e in cited}
        expected_context = next(iter(contexts)) if len(contexts) == 1 else "mixed"
        if claim.context != expected_context or any(e.category != claim.section for e in cited):
            raise InboundValidationError("Claim category or time context misrepresented")
        if claim.metric_aliases:
            if len(claim.metric_aliases) != 1:
                raise InboundValidationError("Only one metric per claim is supported")
            metric = metrics[claim.metric_aliases[0]]
            if set(claim.source_aliases) != set(metric.source_aliases):
                raise InboundValidationError("Metric supporting citations do not match")
            expected_text = metric_claim_text(metric)
        else:
            if len(cited) != 1:
                raise InboundValidationError("Only one evidence record per extractive claim is supported")
            expected_text = evidence_claim_text(cited[0])
        if claim.text != expected_text:
            raise InboundValidationError("Claim text is not deterministically supported")
        key = (claim.section, claim.text, tuple(sorted(claim.source_aliases)))
        if key in seen:
            raise InboundValidationError("Duplicate claim")
        seen.add(key)

    # Conservative extractive mode requires every prepared source and supported
    # metric to survive. Empty output is valid only for empty evidence.
    if {s for c in output.claims if not c.metric_aliases for s in c.source_aliases} != set(sources):
        raise InboundValidationError("Provider omitted supplied evidence")
    if {m for c in output.claims for m in c.metric_aliases} != {
        m.metric_alias for m in payload.metrics if m.source_aliases
    }:
        raise InboundValidationError("Provider omitted a supported metric")
