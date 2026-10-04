"""Fail-closed text boundary. Exact reviewed replacements are not a PII detector."""

import re
from dataclasses import dataclass, field


class PrivacyRejected(ValueError):
    pass


# Defence in depth only; this cannot detect every name or identifying detail.
IDENTIFIERS = re.compile(
    r"\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b|"
    r"[\w.+-]+@[\w.-]+\.[a-z]{2,}|https?://|"
    r"\b(?:\d[ -]?){10,}\b",
    re.I,
)


def check_text(text: str) -> None:
    if IDENTIFIERS.search(text):
        raise PrivacyRejected("Text contains a blocked identifier pattern")


@dataclass(frozen=True)
class ReviewedTextPolicy:
    """Request-local exact source text -> reviewed, minimised replacement.

    Empty by default: all source strings are rejected. Populate only from a
    trusted review or synthetic fixture, never from model output/client input.
    Mappings stay internal. This is not automatic clinical de-identification.
    """

    replacements: dict[str, str] = field(default_factory=dict, repr=False)

    def minimise(self, text: str) -> str:
        replacement = self.replacements.get(text)
        if replacement is None or not replacement.strip():
            raise PrivacyRejected("Source text has no approved minimised replacement")
        check_text(replacement)
        return replacement
