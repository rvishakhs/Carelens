"""Step 8.8: validate and resolve citations within the authorised request."""

from intelligence.core.contracts import Claim
from intelligence.handover.contracts import HandoverSection, ValidatedHandoverContent
from intelligence.handover.input_validation import validate_internal_input

from .contracts import HandoverOutput
from .preparation import PreparedHandover
from .validation import InboundValidationError, validate_inbound_output


def resolve_handover(*, prepared: PreparedHandover, output: HandoverOutput) -> ValidatedHandoverContent:
    # Recheck scope and evidence in case mutable nested input was modified.
    validate_internal_input(prepared.input)
    validate_inbound_output(output=output, payload=prepared.payload)
    if prepared.aliases.resolve_resident(output.resident_alias) != prepared.input.resident_id:
        raise InboundValidationError("Resident mapping does not match the request")
    evidence = prepared.input.retrieval.evidence
    allowed = {
        r.reference
        for r in (
            *evidence.shift_records,
            *evidence.date_context,
            *evidence.unknown_time_records,
        )
    }
    for alias, reference in prepared.source_bindings:
        if prepared.aliases.resolve_source(alias) != reference:
            raise InboundValidationError("Source mapping changed after preparation")
    sections = {}
    for claim in output.claims:
        refs = tuple(prepared.aliases.resolve_source(s) for s in claim.source_aliases)
        if any(ref not in allowed for ref in refs):
            raise InboundValidationError("Source mapping is outside the authorised evidence")
        # Keep resident identity in trusted draft metadata. Do not substitute
        # identity strings into model prose using global text replacement.
        sections.setdefault(claim.section, []).append(Claim(text=claim.text, sources=refs))
    return ValidatedHandoverContent(
        sections=tuple(HandoverSection(category=k, claims=tuple(v)) for k, v in sections.items()),
        warnings=prepared.warnings,
        coverage_complete=prepared.input.retrieval.coverage_complete,
    )
