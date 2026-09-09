from datetime import UTC, datetime

from intelligence.agents.base import AgentContext
from intelligence.core.contracts import AgentId, RunRequest, RunResult, Scope
from intelligence.core.errors import AccessDenied
from intelligence.core.policy import require_access


class CareAgent:
    def __init__(self, agent_id: AgentId, permission: str) -> None:
        self.agent_id = agent_id
        self.permission = permission

    async def run(self, scope: Scope, request: RunRequest, context: AgentContext) -> RunResult:
        require_access(scope, request.resident_id, self.permission)
        bundle = await context.reader.retrieve(scope, request.resident_id, request.period)
        if any(
            r.tenant_id != scope.tenant_id or r.resident_id != request.resident_id for r in bundle.records
        ):
            raise AccessDenied
        handover = self.agent_id == AgentId.HANDOVER
        claims = await context.gateway.summarise(bundle, "handover" if handover else "history")
        return RunResult(
            agent_id=self.agent_id,
            resident_id=request.resident_id,
            period=request.period,
            state="draft" if handover else "completed",
            generated_at=datetime.now(UTC),
            data_cutoff=bundle.retrieved_at,
            coverage_complete=bundle.complete,
            claims=claims,
            warnings=(
                *bundle.warnings,
                "Fake provider: question text is not interpreted or sent.",
                "Demo supports synthetic fluid totals only, not the complete pilot case pack.",
                "No finalisation, clinical guidance or authoritative record writes.",
            ),
        )
