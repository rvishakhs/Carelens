from openai import AsyncOpenAI

from intelligence.gateway.contracts import (
    HandoverOutput,
    HandoverPayload,
)

HANDOVER_SYSTEM_PROMPT = """
You generate structured elderly-care handover claims from the supplied
pseudonymised evidence.

Rules:

1. Use only information explicitly contained in the supplied payload.
2. Do not invent clinical events, measurements, observations, diagnoses,
   causes, risks, treatments, or actions.
3. Every claim must reference one or more source aliases supplied in the
   input.
4. Never create a source alias.
5. Use the supplied resident alias exactly.
6. Preserve uncertainty and evidence quality.
7. Date-context evidence must not be described as definitely occurring
   during the shift.
8. Unknown-time evidence must not be assigned to a specific shift time.
9. Ambiguous or partial metrics must not be described as complete totals.
10. Do not attempt to identify the resident, staff, relatives, or other
    pseudonymised persons.
11. Return only information conforming to the required structured output
    schema.
"""


class OpenAIHandoverProvider:
    def __init__(
        self,
        *,
        client: AsyncOpenAI,
        model: str,
    ) -> None:
        self._client = client
        self._model = model

    async def generate(
        self,
        payload: HandoverPayload,
    ) -> HandoverOutput:
        response = await self._client.responses.parse(
            model=self._model,
            instructions=HANDOVER_SYSTEM_PROMPT,
            input=payload.model_dump_json(),
            text_format=HandoverOutput,
        )

        output = response.output_parsed

        if output is None:
            raise RuntimeError("OpenAI returned no structured handover output")

        return output
