"""Replaces identifying free text with a stable per-resident token before anything
reaches an LLM prompt, and reverses the substitution on the response.

The regex pass below is a starting point, not a guarantee. It must be unit-tested
against a fixture file of nasty edge cases (names inside notes, "Mrs T.", relatives'
names) before Phase 1 is done -- that fixture suite is the actual spec, not this
docstring. A spaCy NER pass is the planned second layer; until it lands, this is
tracked as an open item in governance/hazard-log.md.
"""

import re
import uuid

from app.modules.ai_gateway.ports import RESIDENT_PLACEHOLDER
from app.modules.ai_gateway.repository import PseudonymMappingRepository

_NHS_NUMBER = re.compile(r"\b\d{3}[ -]?\d{3}[ -]?\d{4}\b")
_UK_PHONE = re.compile(r"\b0\d{3,4}[ -]?\d{3}[ -]?\d{3,4}\b")
_DATE_LIKE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")


class Pseudonymiser:
    def __init__(self, mapping_repository: PseudonymMappingRepository):
        self._mapping_repository = mapping_repository

    async def pseudonymise(self, care_home_id: uuid.UUID, resident_id: uuid.UUID, text: str) -> tuple[str, str]:
        """Returns (token, pseudonymised_text). The caller holds `token` in memory only
        long enough to re-identify the response -- it is never persisted alongside the
        LLM output."""
        token = await self._mapping_repository.get_or_create_token(care_home_id, resident_id)
        text = text.replace(RESIDENT_PLACEHOLDER, token)
        return token, self._strip_known_pii_patterns(text)

    def _strip_known_pii_patterns(self, text: str) -> str:
        text = _NHS_NUMBER.sub("[NHS_NUMBER]", text)
        text = _UK_PHONE.sub("[PHONE]", text)
        text = _DATE_LIKE.sub("[DATE]", text)
        return text

    def re_identify(self, token: str, real_value: str, text: str) -> str:
        return text.replace(token, real_value)
