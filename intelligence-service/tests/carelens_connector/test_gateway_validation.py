import pytest

from intelligence.gateway.validation import (
    GatewayValidationError,
    InboundValidationError,
    OutboundValidationError,
    validate_outbound_payload
)
from intelligence.gateway.contracts import HandoverPayload, PseudonymisedEvidence

def make_payload(
    *,
    resident_alias: str = "RESIDENT_001",
    source_aliases: tuple[str, ...] = ("SRC_001",),
) -> HandoverPayload:
    evidence = tuple(
        PseudonymisedEvidence(
            source_alias=source_alias,
            category="mobility",
            time_label=(
                "Clinical event time: "
                "2026-09-28T10:00:00+01:00"
            ),
            time_precision="timestamp",
            content="Resident walked with staff assistance.",
        )
        for source_alias in source_aliases
    )

    return HandoverPayload(
        resident_alias=resident_alias,
        period_label="2026-09-28 day shift",
        evidence=evidence,
        metrics=(),
    )

def test_outbound_validation_error_is_gateway_error():
    error = OutboundValidationError("Outbound payload rejected")

    assert isinstance(error, GatewayValidationError)


def test_inbound_validation_error_is_gateway_error():
    error = InboundValidationError("Provider response rejected")

    assert isinstance(error, GatewayValidationError)


@pytest.mark.parametrize(
    "error_type",
    [
        OutboundValidationError,
        InboundValidationError,
    ],
)
def test_validation_errors_are_value_errors(error_type):
    assert issubclass(error_type, ValueError)

def test_valid_outbound_payload_passes():
    payload = make_payload(
        resident_alias="RESIDENT_001",
        source_aliases=("SRC_001", "SRC_002"),
    )

    validate_outbound_payload(payload)

def test_invalid_resident_alias_is_rejected():
    payload = make_payload(
        resident_alias="REAL_RESIDENT_ID",
        source_aliases=("SRC_001",),
    )

    with pytest.raises(
        OutboundValidationError,
        match="invalid resident alias",
    ):
        validate_outbound_payload(payload)

def test_invalid_source_alias_is_rejected():
    payload = make_payload(
        resident_alias="RESIDENT_001",
        source_aliases=("REAL_SOURCE_ID",),
    )

    with pytest.raises(
        OutboundValidationError,
        match="invalid source alias",
    ):
        validate_outbound_payload(payload)

def test_duplicate_source_alias_is_rejected():
    payload = make_payload(
        resident_alias="RESIDENT_001",
        source_aliases=("SRC_001", "SRC_001"),
    )

    with pytest.raises(
        OutboundValidationError,
        match="duplicate source aliases",
    ):
        validate_outbound_payload(payload)