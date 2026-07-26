"""The orchestration from the Phase 1 architecture doc:

summaries --> ai_gateway.complete() --> pseudonymiser --> LLMProvider port --> adapter
                                              |
                                  mapping table (DB only)
                                              |
                                re-identify response <--
"""

import uuid

from app.modules.ai_gateway.ports import LLMProvider
from app.modules.ai_gateway.pseudonymiser import Pseudonymiser


class AIGatewayService:
    def __init__(self, llm_provider: LLMProvider, pseudonymiser: Pseudonymiser):
        self._llm_provider = llm_provider
        self._pseudonymiser = pseudonymiser

    async def complete(
        self,
        *,
        care_home_id: uuid.UUID,
        resident_id: uuid.UUID,
        resident_display_name: str,
        prompt: str,
        model: str | None = None,
    ) -> str:
        token, safe_prompt = await self._pseudonymiser.pseudonymise(care_home_id, resident_id, prompt)
        raw_response = await self._llm_provider.complete(safe_prompt, model=model)
        return self._pseudonymiser.re_identify(token, resident_display_name, raw_response)
