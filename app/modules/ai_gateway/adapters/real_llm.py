"""Real provider adapter. Phase 1 uses dev keys against synthetic data only, purely to
prove the gateway path end-to-end -- provider selection + DPA review is Phase 2 (see
governance/decision-log.md). Swapping providers here is a config change in
container.py, not a refactor of any consuming module."""

from app.modules.ai_gateway.ports import LLMProvider


class RealLLMProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise RuntimeError("LLM_API_KEY is required when LLM_PROVIDER is not 'fake' or 'local'")
        self._api_key = api_key
        self._model = model

    async def complete(self, prompt: str, *, model: str | None = None) -> str:
        raise NotImplementedError(
            "Wire up the chosen provider's completion API here once selected in "
            "Phase 2 -- see governance/decision-log.md for the pending decision."
        )
