from dataclasses import dataclass
from typing import Literal

from sqlalchemy import text

from intelligence.connectors.carelens import (
    CareLensAccessDenied,
    CareLensUnavailable,
)
from intelligence.core.errors import (
    ExecutionAuthorisationDenied,
    ExecutionAuthorisationUnavailable,
    GatewayRejected,
    HandoverLeaseLost,
    HandoverLeaseUncertain
)
from intelligence.gateway.handover import HandoverProviderTimeout
from intelligence.gateway.privacy import PrivacyRejected
from intelligence.gateway.validation import (
    InboundValidationError,
    OutboundValidationError,
)
from intelligence.persistence.database import Database
from intelligence.persistence.job_repository import (
    ClaimedJob,
    mark_handover_job_failed,
    retry_handover_job,
)



@dataclass(frozen=True)
class FailureDecision:
    action: Literal["retry", "fail", "leave"]
    code: str


def classify_one(error: Exception) -> FailureDecision:
    if isinstance(error, HandoverLeaseUncertain):
        return FailureDecision("leave", "lease_uncertain")

    if isinstance(error, HandoverLeaseLost):
        return FailureDecision("leave", "lease_lost")

    if isinstance(
        error,
        (ExecutionAuthorisationDenied, CareLensAccessDenied),
    ):
        return FailureDecision("fail", "authorisation_denied")

    if isinstance(
        error,
        (PrivacyRejected, GatewayRejected, OutboundValidationError),
    ):
        return FailureDecision("fail", "gateway_rejected")

    if isinstance(error, InboundValidationError):
        return FailureDecision("fail", "invalid_provider_output")

    if isinstance(error, HandoverProviderTimeout):
        return FailureDecision("retry", "provider_timeout")

    if isinstance(error, ExecutionAuthorisationUnavailable):
        return FailureDecision("retry", "authorisation_unavailable")

    if isinstance(error, CareLensUnavailable):
        return FailureDecision("retry", "connector_unavailable")

    return FailureDecision("fail", "internal_error")


def classify_failure(error: Exception) -> FailureDecision:
    # TaskGroup can wrap errors in nested ExceptionGroups.
    if not isinstance(error, ExceptionGroup):
        return classify_one(error)

    decisions = [
        classify_failure(child)
        for child in error.exceptions
    ]

    # Lost ownership takes priority. Never overwrite another attempt.
    for action in ("leave", "fail", "retry"):
        for decision in decisions:
            if decision.action == action:
                return decision

    return FailureDecision("fail", "internal_error")


async def record_execution_failure(
    db: Database,
    *,
    claim: ClaimedJob,
    decision: FailureDecision,
) -> str:
    if decision.action == "leave":
        return "unchanged"


    # A fresh transaction, independent of the failed processing.
    async with db.session() as session:
        async with session.begin():
            await session.execute(
                text(
                    "SELECT set_config("
                    "'intelligence.tenant_id', :tenant_id, true)"
                ),
                {"tenant_id": str(claim.tenant_id)},
            )

            if decision.action == "retry":
                outcome = await retry_handover_job(
                    session,
                    claim=claim,
                    failure_code=decision.code,
                    delay_seconds=30,
                )
            else:
                changed = await mark_handover_job_failed(
                    session,
                    claim=claim,
                    failure_code=decision.code,
                )
                outcome = "failed" if changed else "not_owned"

        # Return only after the transaction commits.
        return outcome
