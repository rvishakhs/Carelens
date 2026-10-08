"""Provider composition boundary: add future use-case routing here, not in agents."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from openai import AsyncOpenAI

from intelligence.config import HandoverProviderSettings, OpenAIProviderSettings
from intelligence.gateway.contracts import HandoverProvider, Provider
from intelligence.providers.openai_handover import OpenAIHandoverProvider
from intelligence.providers.openai_structured import OpenAIStructuredProvider


@dataclass(frozen=True)
class ProviderRuntime:
    handover: HandoverProvider
    structured: Provider
    provider: str
    model: str
    timeout_seconds: float
    prompt_version: str = "openai-supported-prose-v2"


@asynccontextmanager
async def open_provider_runtime() -> AsyncIterator[ProviderRuntime]:
    # Validate configured routing; unsupported providers never silently fall back.
    HandoverProviderSettings()
    settings = OpenAIProviderSettings()
    async with AsyncOpenAI(
        api_key=settings.api_key.get_secret_value(),
        base_url="https://api.openai.com/v1",
        timeout=settings.timeout_seconds,
        max_retries=0,
    ) as client:
        yield ProviderRuntime(
            handover=OpenAIHandoverProvider(
                client=client,
                model=settings.model,
                max_output_tokens=settings.max_output_tokens,
            ),
            structured=OpenAIStructuredProvider(
                client=client,
                model=settings.model,
                max_output_tokens=settings.max_output_tokens,
            ),
            provider="openai",
            model=settings.model,
            timeout_seconds=settings.timeout_seconds,
        )
