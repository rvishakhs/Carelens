"""Phase 1 NoteStructurer adapter: keyword/regex rules only, no LLM call on the
ingestion path. Swapping in an LLM-backed structurer later is a container.py change."""

import re

from app.modules.observations.ports import NoteStructurer

_MOOD_KEYWORDS = {
    "low": ["tearful", "withdrawn", "low mood", "upset"],
    "settled": ["settled", "calm", "content"],
    "agitated": ["agitated", "distressed", "confused", "restless"],
}
_REFUSAL_PATTERN = re.compile(r"\brefus(ed|ing|es)\b", re.IGNORECASE)
_FALL_PATTERN = re.compile(r"\bfell\b|\bfall\b|\bfound on (the )?floor\b", re.IGNORECASE)


class RuleBasedNoteStructurer(NoteStructurer):
    async def structure(self, text: str) -> dict:
        lowered = text.lower()
        mood = next((label for label, keywords in _MOOD_KEYWORDS.items() if any(k in lowered for k in keywords)), None)
        return {
            "mood": mood,
            "refusal_mentioned": bool(_REFUSAL_PATTERN.search(text)),
            "fall_mentioned": bool(_FALL_PATTERN.search(text)),
        }
