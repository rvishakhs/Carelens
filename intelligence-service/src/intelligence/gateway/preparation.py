"""Steps 8.4–8.6: prepare a bounded provider payload and private request state."""

import json
from dataclasses import dataclass, field

from pydantic import ValidationError

from intelligence.core.contracts import SourceRef
from intelligence.handover.contracts import HandoverAgentInput
from intelligence.handover.input_validation import validate_internal_input
from intelligence.handover.rendering import render_evidence

from .contracts import CalculatedMetric, HandoverPayload, PseudonymisedEvidence
from .privacy import ReviewedTextPolicy
from .pseudonymisation import AliasContext
from .validation import OutboundValidationError, validate_outbound_payload


@dataclass(frozen=True)
class PreparedHandover:
    # Never log/serialize the wrapper; only payload crosses the boundary.
    payload: HandoverPayload
    aliases: AliasContext = field(repr=False)
    input: HandoverAgentInput = field(repr=False)
    warnings: tuple[str, ...] = field(repr=False)
    source_bindings: tuple[tuple[str, SourceRef], ...] = field(repr=False)


def prepare_handover(
    *, input: HandoverAgentInput, text_policy: ReviewedTextPolicy | None = None
) -> PreparedHandover:
    # Detach mutable nested clinical dictionaries from the caller.
    input = HandoverAgentInput.model_validate_json(input.model_dump_json())
    validate_internal_input(input)
    policy = text_policy or ReviewedTextPolicy()
    aliases = AliasContext()
    resident_alias = aliases.alias_resident(input.resident_id)
    evidence = input.retrieval.evidence
    warnings = [*input.retrieval.warnings, *evidence.warnings, *input.metrics.warnings]
    provider_evidence = []
    records = (*evidence.shift_records, *evidence.date_context, *evidence.unknown_time_records)
    try:
        for record in records:
            rendered = render_evidence(record, care_home_timezone=input.care_home_timezone)
            warnings.extend(rendered.warnings)
            fields = {}
            for item in rendered.fields:
                fields[item.name] = policy.minimise(item.value) if isinstance(item.value, str) else item.value
            # Empty records retain provenance and an explicit quality warning.
            content = json.dumps(fields, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            provider_evidence.append(
                PseudonymisedEvidence(
                    source_alias=aliases.alias_source(record.reference),
                    category=rendered.category,
                    context=rendered.context,
                    time_precision=rendered.time_precision,
                    time_label=rendered.time_label,
                    content=content,
                    quality_warnings=rendered.warnings,
                )
            )
        metrics = []
        for index, (name, metric) in enumerate(
            (
                ("consumed_ml", input.metrics.consumed),
                ("offered_ml", input.metrics.offered),
            ),
            1,
        ):
            metrics.append(
                CalculatedMetric(
                    metric_alias=f"METRIC_{index:03d}",
                    metric=name,
                    status=metric.status,
                    value=metric.value,
                    known_subtotal=metric.known_subtotal,
                    source_aliases=tuple(aliases.alias_source(s) for s in metric.sources),
                )
            )
        # Raw retrieval warnings stay internal; they may include source details.
        # Send only controlled messages, never arbitrary exception/provider text.
        provider_warnings = []
        if not input.retrieval.coverage_complete:
            provider_warnings.append("Retrieval coverage is incomplete.")
        if warnings:
            provider_warnings.append("Internal evidence warnings require reviewer attention.")
        payload = HandoverPayload(
            resident_alias=resident_alias,
            period_label=(
                f"{input.period.start.isoformat()} to "
                f"{input.period.end.isoformat()} (end exclusive)"
            ),
            evidence=tuple(provider_evidence),
            metrics=tuple(metrics),
            coverage_complete=input.retrieval.coverage_complete,
            coverage_warnings=tuple(provider_warnings),
        )
    except ValidationError:
        raise OutboundValidationError("Prepared payload violates provider contract") from None
    validate_outbound_payload(payload)
    bindings = tuple((e.source_alias, aliases.resolve_source(e.source_alias)) for e in payload.evidence)
    return PreparedHandover(payload, aliases, input, tuple(dict.fromkeys(warnings)), bindings)
