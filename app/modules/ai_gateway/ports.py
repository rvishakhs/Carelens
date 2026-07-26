"""LLMProvider is the one port every AI call in the app goes through. Three adapters
ship in Phase 1: FakeLLM (tests), LocalLLM (optional Ollama for dev), and a real
provider (dev keys, synthetic data only, to prove the path end-to-end). Selecting
between them is a config change (settings.llm_provider) -- never a code change in a
consuming module."""

import abc

# Callers build prompts referring to the resident only by this placeholder -- never
# the real name. Pseudonymiser.pseudonymise() substitutes it with the stable per-
# resident token right before the prompt leaves the process.
RESIDENT_PLACEHOLDER = "{{RESIDENT}}"


class LLMProvider(abc.ABC):
    @abc.abstractmethod
    async def complete(self, prompt: str, *, model: str | None = None) -> str: ...
