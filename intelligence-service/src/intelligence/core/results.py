from time import monotonic
from uuid import UUID

from intelligence.core.contracts import RunResult, Scope
from intelligence.core.errors import CapacityExceeded


class MemoryResults:
    """Bounded local demo storage. Not durable; no clinical records or conversations stored."""

    def __init__(self, ttl: int, capacity: int) -> None:
        self.ttl = ttl
        self.capacity = capacity
        self._rows: dict[UUID, tuple[float, UUID, UUID, RunResult, str]] = {}

    def _prune(self) -> None:
        now = monotonic()
        self._rows = {k: v for k, v in self._rows.items() if v[0] > now}

    def put(self, scope: Scope, result: RunResult, permission: str) -> None:
        self._prune()
        if len(self._rows) >= self.capacity:
            raise CapacityExceeded
        self._rows[result.run_id] = (
            monotonic() + self.ttl,
            scope.tenant_id,
            scope.actor_id,
            result,
            permission,
        )

    def get(self, scope: Scope, run_id: UUID) -> RunResult | None:
        self._prune()
        row = self._rows.get(run_id)
        if row is None or row[1:3] != (scope.tenant_id, scope.actor_id):
            return None
        result = row[3]
        if result.resident_id not in scope.resident_ids or not {row[4], "evidence:read"} <= scope.permissions:
            return None
        return result
