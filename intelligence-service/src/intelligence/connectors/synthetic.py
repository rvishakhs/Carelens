from datetime import UTC, datetime
from uuid import UUID

from intelligence.core.contracts import Evidence, EvidenceBundle, Period, Scope, SourceRef
from intelligence.core.errors import AccessDenied
from intelligence.core.policy import require_access

TENANT_ID = UUID("10000000-0000-0000-0000-000000000001")
ACTOR_ID = UUID("20000000-0000-0000-0000-000000000001")
RESIDENT_ID = UUID("30000000-0000-0000-0000-000000000001")


def demo_scope() -> Scope:
    return Scope(
        tenant_id=TENANT_ID,
        actor_id=ACTOR_ID,
        resident_ids=frozenset({RESIDENT_ID}),
        permissions=frozenset({"evidence:read", "history:run", "handover:generate"}),
    )


def fixture_records() -> tuple[Evidence, ...]:
    return tuple(
        Evidence(
            tenant_id=TENANT_ID,
            resident_id=RESIDENT_ID,
            reference=SourceRef(
                source_type="fluid_intake_records",
                source_id=UUID(f"40000000-0000-0000-0000-{i:012d}"),
                version="fixture-v1",
            ),
            effective_at=datetime(2026, 9, 8, hour, tzinfo=UTC),
            recorded_at=datetime(2026, 9, 8, hour, tzinfo=UTC),
            time_basis="effective",
            time_precision="timestamp",
            kind="fluid",
            consumed_ml=consumed,
            offered_ml=offered,
        )
        for i, (hour, offered, consumed) in enumerate([(8, 200, 150), (12, 280, 200), (16, 150, 100)], 1)
    )


class SyntheticEvidenceReader:
    async def retrieve(self, scope: Scope, resident_id: UUID, period: Period) -> EvidenceBundle:
        require_access(scope, resident_id, "evidence:read")
        if scope.tenant_id != TENANT_ID:
            raise AccessDenied
        rows = tuple(
            r
            for r in fixture_records()
            if r.resident_id == resident_id
            and r.effective_at is not None
            and period.start <= r.effective_at < period.end
        )
        return EvidenceBundle(
            records=rows,
            retrieved_at=datetime.now(UTC),
            complete=True,
            warnings=("Synthetic fixture coverage only; no live CareLens data connected.",),
        )
