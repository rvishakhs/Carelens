"""Adapter for an Ollama-style local model -- optional, dev-only, so no data leaves
the machine while iterating on prompts. Selected via LLM_PROVIDER=local."""

import httpx

from app.modules.ai_gateway.ports import LLMProvider


class LocalLLMProvider(LLMProvider):
    def __init__(self, model: str, base_url: str = "http://localhost:11434"):
        self._model = model
        self._base_url = base_url

    async def complete(self, prompt: str, *, model: str | None = None) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._base_url}/api/generate",
                json={"model": model or self._model, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            return response.json()["response"]
