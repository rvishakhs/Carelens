"""Request-scoped pseudonymisation for handover generation.

This module aliases structured internal identifiers before data is sent
across the provider boundary.

Important:
- Alias mappings exist only for one generation request.
- Providers receive aliases, never the mapping.
- This does NOT sanitise identifiers embedded inside free text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from intelligence.core.contracts import SourceRef


class PseudonymisationError(ValueError):
    """Base error for pseudonymisation failures."""


class UnknownAliasError(PseudonymisationError):
    """Raised when an alias does not belong to this request."""

def _source_key(reference: SourceRef) -> tuple[str, str, str, str]:
    return (
        reference.source_system,
        reference.source_type,
        str(reference.source_id),
        reference.version,
    )

@dataclass
class AliasContext:
    """Request-scoped mapping between aliases and internal identities.

    Create a new instance for every handover-generation request.
    Never reuse an AliasContext between requests.
    """

    _resident_to_alias: dict[UUID, str] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _alias_to_resident: dict[str, UUID] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    _source_to_alias: dict[SourceRef, str] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _alias_to_source: dict[str, SourceRef] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _source_to_alias: dict[tuple[str, str, str, str], str]

    def alias_resident(self, resident_id: UUID) -> str:
        """Return a stable alias for this resident within this request."""

        existing = self._resident_to_alias.get(resident_id)

        if existing is not None:
            return existing

        alias = f"RESIDENT_{len(self._resident_to_alias) + 1:03d}"

        self._resident_to_alias[resident_id] = alias
        self._alias_to_resident[alias] = resident_id

        return alias

    def alias_source(self, reference: SourceRef) -> str:
        """Return a stable alias for a complete SourceRef."""

        # existing = self._source_to_alias.get(reference)
        #
        # if existing is not None:
        #     return existing
        #
        # alias = f"SRC_{len(self._source_to_alias) + 1:03d}"
        #
        # self._source_to_alias[reference] = alias
        # self._alias_to_source[alias] = reference

        key = _source_key(reference)

        existing = self._source_to_alias.get(key)

        if existing is not None:
            return existing

        alias = f"SRC_{len(self._source_to_alias) + 1:03d}"

        self._source_to_alias[key] = alias
        self._alias_to_source[alias] = reference

        return alias

    def resolve_resident(self, alias: str) -> UUID:
        """Resolve a resident alias created by this context."""

        resident_id = self._alias_to_resident.get(alias)

        if resident_id is None:
            raise UnknownAliasError("Unknown resident alias")

        return resident_id

    def resolve_source(self, alias: str) -> SourceRef:
        """Resolve a source alias created by this context."""

        reference = self._alias_to_source.get(alias)

        if reference is None:
            raise UnknownAliasError("Unknown source alias")

        return reference

    def knows_resident_alias(self, alias: str) -> bool:
        return alias in self._alias_to_resident

    def knows_source_alias(self, alias: str) -> bool:
        return alias in self._alias_to_source

