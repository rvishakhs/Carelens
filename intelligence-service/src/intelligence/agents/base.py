from dataclasses import dataclass
from typing import Protocol

from intelligence.core.contracts import AgentId, RunRequest, RunResult, Scope
from intelligence.core.ports import EvidenceReader
from intelligence.gateway.service import Gateway


@dataclass(frozen=True)
class AgentContext:
    reader: EvidenceReader
    gateway: Gateway


class Agent(Protocol):
    agent_id: AgentId
    permission: str

    async def run(self, scope: Scope, request: RunRequest, context: AgentContext) -> RunResult: ...
