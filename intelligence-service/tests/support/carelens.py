"""Synthetic CareLens transport records; never real credentials."""

from datetime import datetime
from uuid import UUID

from pydantic import SecretStr

from intelligence.connectors.carelens import ObservationResponse
from intelligence.core.contracts import ExecutionContext

TENANT_ID = UUID("10000000-0000-0000-0000-000000000001")
RESIDENT_ID = UUID("30000000-0000-0000-0000-000000000001")
OTHER_RESIDENT_ID = UUID("30000000-0000-0000-0000-000000000002")
OTHER_ID = OTHER_RESIDENT_ID
TOKEN = SecretStr("synthetic-test-token-not-a-real-credential")
SINCE = datetime.fromisoformat("2026-09-08T07:00:00+01:00")
UNTIL = datetime.fromisoformat("2026-09-08T19:00:00+01:00")


def context() -> ExecutionContext:
    return ExecutionContext(
        tenant_id=TENANT_ID,
        service_identity="synthetic-test-service",
        trigger="scheduled",
        authorised_resident_ids=frozenset({RESIDENT_ID}),
        permissions=frozenset({"evidence:read"}),
    )


def observation(**changes) -> ObservationResponse:
    data = {
        "id": "40000000-0000-0000-0000-000000000001",
        "resident_id": str(RESIDENT_ID),
        "type": "fluid_intake",
        "value": {
            "volume_ml": 150,
            "ml": 150,
            "notes": "Synthetic note",
        },
        "recorded_at": "2026-09-08T08:00:00+01:00",
        "recorded_by": None,
        "is_implausible": False,
        "source_type": "fluid_intake_records",
        "time_precision": "timestamp",
        "source_date": None,
    }
    data.update(changes)
    return ObservationResponse.model_validate(data)


def record(**changes):
    return {
        "id": "40000000-0000-0000-0000-000000000001",
        "resident_id": str(RESIDENT_ID),
        "type": "fluid_intake",
        "value": {"volume_ml": 150, "ml": 150, "notes": "synthetic-private-marker"},
        "recorded_at": "2026-09-08T08:00:00+01:00",
        "recorded_by": None,
        "is_implausible": False,
        "source_type": "fluid_intake_records",
        "time_precision": "timestamp",
        "source_date": None,
        **changes,
    }
