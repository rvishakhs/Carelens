"""OpenAI adapter for the existing structured fluid/history contract."""

from openai import AsyncOpenAI

from intelligence.core.errors import GatewayRejected
from intelligence.gateway.contracts import ProviderOutput, SafePayload


class OpenAIStructuredProvider:
    def __init__(self, *, client: AsyncOpenAI, model: str, max_output_tokens: int = 4096):
        self._client = client
        self._model = model
        self._max_output_tokens = max_output_tokens

    async def generate(self, payload: SafePayload) -> ProviderOutput:
        try:
            response = await self._client.responses.parse(
                model=self._model,
                instructions=(
                    "Copy supplied structured metrics exactly. Do not infer values. "
                    "If source_aliases is nonempty return exactly two claims: consumed_ml "
                    "and offered_ml, preserving null values. Each claim must copy the "
                    "resident_alias and all source_aliases. If source_aliases is empty "
                    "return one no_records claim with value null and no source aliases."
                ),
                input=payload.model_dump_json(),
                text_format=ProviderOutput,
                store=False,
                max_output_tokens=self._max_output_tokens,
            )
            if response.status != "completed" or response.output_parsed is None:
                raise GatewayRejected
            return response.output_parsed
        except Exception:
            # Never surface SDK errors containing request or response content.
            raise GatewayRejected from None
