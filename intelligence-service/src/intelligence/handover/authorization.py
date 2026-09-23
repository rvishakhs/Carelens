from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from intelligence.core.contracts import ExecutionContext, Scope
from intelligence.persistence.job_repository import JobExecutionSnapshot
from intelligence.core.errors import AccessDenied, ExecutionAuthorisationDenied, ExecutionAuthorisationUnavailable

@dataclass(frozen=True)
class ServiceGrant:
    tenant_id: UUID
    service_identity: str
    resident_ids: frozenset[UUID]
    permissions: frozenset[str]


@dataclass(frozen=True)
class StaffGrant:
    tenant_id: UUID
    actor_id: UUID
    resident_ids: frozenset[UUID]
    permissions: frozenset[str]



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



class ExecutionAuthorizer(Protocol):
    async def authorise(
        self,
        *,
        job: JobExecutionSnapshot,
    ) -> ExecutionContext:
        """Check current authority before accessing resident evidence.

        Implementations must:
        - Authenticate the executing service independently of the job.
        - Check the service's access to the tenant and resident.
        - Confirm the resident is eligible for handover generation.
        - For manual jobs, check the initiating actor's current access.
        - For scheduled jobs, check scheduling authority.
        - Return permissions obtained from the authority source.

        Raises:
            ExecutionAuthorisationDenied:
                Authority was checked and execution is not permitted.
            ExecutionAuthorisationUnavailable:
                Authority could not be checked due to a temporary failure.
        """
        ...