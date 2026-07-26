"""Deterministic canned adapter for tests and default dev config -- never calls out to
a network. This is what LLM_PROVIDER=fake selects."""

from app.modules.ai_gateway.ports import LLMProvider


class FakeLLMProvider(LLMProvider):
    async def complete(self, prompt: str, *, model: str | None = None) -> str:
        return f"[FAKE_LLM_RESPONSE] generated from {len(prompt)} chars of pseudonymised input"
