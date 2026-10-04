from intelligence.gateway.handover import HandoverGateway
from intelligence.gateway.privacy import ReviewedTextPolicy
from intelligence.handover.contracts import (
    HandoverAgentInput,
    ValidatedHandoverContent,
)


class HandoverAgent:
    agent_id = "handover_draft"
    permission = "handover:generate"
    version = "0.1.0"

    def __init__(self, gateway: HandoverGateway) -> None:
        self._gateway = gateway

    async def generate(
        self,
        *,
        input: HandoverAgentInput,
        text_policy: ReviewedTextPolicy | None = None,
    ) -> ValidatedHandoverContent:
        return await self._gateway.generate(
            input=input,
            text_policy=text_policy,
        )