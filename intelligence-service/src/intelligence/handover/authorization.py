import asyncio
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from intelligence.core.contracts import ExecutionContext, Scope
from intelligence.core.errors import (
    AccessDenied,
    ExecutionAuthorisationDenied,
    ExecutionAuthorisationUnavailable,
)
from intelligence.persistence.job_repository import JobExecutionSnapshot


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


class CareLensAuthorityReader(Protocol):
    """Trusted adapter, authenticated with worker credentials, never job credentials.

    Read fresh authority from CareLens, including tenant/floor/resident restrictions.
    Map explicit refusals to ExecutionAuthorisationDenied and transport/invalid
    responses to ExecutionAuthorisationUnavailable. Never derive grants from jobs.
    """

    async def service_grant(self, *, tenant_id: UUID) -> ServiceGrant: ...

    async def staff_grant(self, *, tenant_id: UUID, actor_id: UUID) -> StaffGrant: ...

    async def resident_eligible(self, *, tenant_id: UUID, resident_id: UUID) -> bool: ...


class CareLensExecutionAuthorizer:
    """Execution policy; the injected reader supplies authenticated current grants.

    ``expected_service_identity`` comes from trusted worker configuration. The
    reader must authenticate that identity independently using its credentials.
    Scheduled grants require the explicit ``handover:schedule`` permission.
    """

    def __init__(
        self,
        reader: CareLensAuthorityReader,
        *,
        expected_service_identity: str,
        timeout_seconds: float = 10,
    ) -> None:
        if not expected_service_identity.strip():
            raise ValueError("An executing service identity is required")
        if not 0 < timeout_seconds <= 30:
            raise ValueError("Authority timeout must be between 0 and 30 seconds")
        self._reader = reader
        self._identity = expected_service_identity
        self._timeout = timeout_seconds

    async def authorise(self, *, job: JobExecutionSnapshot) -> ExecutionContext:
        try:
            async with asyncio.timeout(self._timeout):
                return await self._authorise(job)
        except TimeoutError:
            raise ExecutionAuthorisationUnavailable("Authority check timed out") from None

    async def _authorise(self, job: JobExecutionSnapshot) -> ExecutionContext:
        if (
            job.purpose != "handover_generation"
            or job.service_identity != self._identity
            or job.trigger not in {"manual", "scheduled"}
            or (job.trigger == "manual" and job.initiating_actor_id is None)
            or (job.trigger == "scheduled" and job.initiating_actor_id is not None)
        ):
            raise ExecutionAuthorisationDenied("Invalid execution identity or purpose")

        service = await self._reader.service_grant(tenant_id=job.tenant_id)
        if (
            service.tenant_id != job.tenant_id
            or service.service_identity != self._identity
            or job.resident_id not in service.resident_ids
            or "handover:generate" not in service.permissions
        ):
            raise ExecutionAuthorisationDenied("Service cannot generate this handover")

        permissions = service.permissions
        if job.trigger == "manual":
            assert job.initiating_actor_id is not None
            staff = await self._reader.staff_grant(
                tenant_id=job.tenant_id, actor_id=job.initiating_actor_id,
            )
            if (
                staff.tenant_id != job.tenant_id
                or staff.actor_id != job.initiating_actor_id
                or job.resident_id not in staff.resident_ids
                or "handover:generate" not in staff.permissions
            ):
                raise ExecutionAuthorisationDenied("Staff access is no longer permitted")
            permissions = permissions & staff.permissions
        elif "handover:schedule" not in service.permissions:
            raise ExecutionAuthorisationDenied("Service cannot execute scheduled handovers")

        eligible = await self._reader.resident_eligible(
            tenant_id=job.tenant_id, resident_id=job.resident_id,
        )
        if eligible is not True:
            raise ExecutionAuthorisationDenied("Resident is not eligible for handover")

        return ExecutionContext(
            tenant_id=job.tenant_id,
            initiating_actor_id=job.initiating_actor_id,
            service_identity=service.service_identity,
            trigger=job.trigger,
            purpose=job.purpose,
            authorised_resident_ids=frozenset({job.resident_id}),
            permissions=permissions,
        )


