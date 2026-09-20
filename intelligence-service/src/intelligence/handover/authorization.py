from uuid import UUID

from intelligence.core.contracts import ExecutionContext, Scope
from intelligence.core.errors import AccessDenied


def authorise_manual_handover(
    scope: Scope,
    *,
    resident_id: UUID,
    service_identity: str,
) -> ExecutionContext:
    if "handover:generate" not in scope.permissions:
        raise AccessDenied

    if resident_id not in scope.resident_ids:
        raise AccessDenied

    return ExecutionContext(
        tenant_id=scope.tenant_id,
        initiating_actor_id=scope.actor_id,
        service_identity=service_identity,
        trigger="manual",
        purpose="handover_generation",
        authorised_resident_ids=frozenset({resident_id}),
        permissions=scope.permissions,
    )