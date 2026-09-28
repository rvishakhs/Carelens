"""Validation for data crossing the external provider boundary."""




from .contracts import HandoverPayload


class GatewayValidationError(ValueError):
    """Base error for gateway validation failures."""


class OutboundValidationError(GatewayValidationError):
    """Provider-bound payload failed validation."""


class InboundValidationError(GatewayValidationError):
    """Provider response failed validation."""


def validate_outbound_payload(payload: HandoverPayload) -> None:
    """Validate the structure of a provider-bound handover payload.

    This function is the final structural gate before provider dispatch.

    It does not currently perform free-text PII detection. That is handled
    by later pseudonymisation/minimisation stages.

    Raises:
        OutboundValidationError:
            If the payload violates the outbound gateway contract.
    """

    if not payload.resident_alias.strip():
        raise OutboundValidationError(
            "Outbound payload has no resident alias"
        )

    if not payload.resident_alias.startswith("RESIDENT_"):
        raise OutboundValidationError(
            "Outbound payload contains an invalid resident alias"
        )

    seen_source_aliases: set[str] = set()

    for evidence in payload.evidence:
        source_alias = evidence.source_alias

        if not source_alias.strip():
            raise OutboundValidationError(
                "Outbound evidence has no source alias"
            )

        if not source_alias.startswith("SRC_"):
            raise OutboundValidationError(
                "Outbound evidence contains an invalid source alias"
            )

        if source_alias in seen_source_aliases:
            raise OutboundValidationError(
                "Outbound payload contains duplicate source aliases"
            )

        seen_source_aliases.add(source_alias)