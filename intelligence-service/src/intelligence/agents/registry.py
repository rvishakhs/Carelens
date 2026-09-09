from intelligence.agents.base import Agent
from intelligence.agents.care import CareAgent
from intelligence.core.contracts import AgentId


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[AgentId, Agent] = {}

    def register(self, agent: Agent) -> None:
        if agent.agent_id in self._agents:
            raise ValueError("duplicate agent ID")
        self._agents[agent.agent_id] = agent

    def get(self, agent_id: AgentId) -> Agent:
        return self._agents[agent_id]

    def describe(self) -> list[dict[str, str]]:
        return [
            {"id": str(a.agent_id), "permission": a.permission, "mode": "synthetic"}
            for a in self._agents.values()
        ]


def default_registry() -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(CareAgent(AgentId.HISTORY, "history:run"))
    registry.register(CareAgent(AgentId.HANDOVER, "handover:generate"))
    return registry
