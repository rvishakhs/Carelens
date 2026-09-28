from uuid import uuid4

import pytest

from intelligence.core.contracts import SourceRef
from intelligence.gateway.pseudonymisation import (
    AliasContext,
    UnknownAliasError,
)


def make_source(
    *,
    source_type: str = "mobility_observations",
    source_id=None,
) -> SourceRef:
    return SourceRef(
        source_system="Carelens_connector",
        source_type=source_type,
        source_id=source_id or uuid4(),
        version="unversioned",
    )


def test_resident_gets_request_scoped_alias():
    context = AliasContext()
    resident_id = uuid4()

    alias = context.alias_resident(resident_id)

    assert alias == "RESIDENT_001"
    assert context.resolve_resident(alias) == resident_id


def test_same_resident_returns_same_alias():
    context = AliasContext()
    resident_id = uuid4()

    first = context.alias_resident(resident_id)
    second = context.alias_resident(resident_id)

    assert first == second


def test_source_can_be_resolved():
    context = AliasContext()
    source = make_source()

    alias = context.alias_source(source)

    assert alias == "SRC_001"
    assert context.resolve_source(alias) == source


def test_same_source_returns_same_alias():
    context = AliasContext()
    source = make_source()

    first = context.alias_source(source)
    second = context.alias_source(source)

    assert first == second


def test_same_uuid_in_different_tables_gets_different_alias():
    context = AliasContext()

    shared_id = uuid4()

    mobility = make_source(
        source_type="mobility_observations",
        source_id=shared_id,
    )

    fall = make_source(
        source_type="falls_incidents",
        source_id=shared_id,
    )

    mobility_alias = context.alias_source(mobility)
    fall_alias = context.alias_source(fall)

    assert mobility_alias != fall_alias

    assert context.resolve_source(mobility_alias) == mobility
    assert context.resolve_source(fall_alias) == fall


def test_unknown_source_alias_fails():
    context = AliasContext()

    with pytest.raises(UnknownAliasError):
        context.resolve_source("SRC_999")


def test_unknown_resident_alias_fails():
    context = AliasContext()

    with pytest.raises(UnknownAliasError):
        context.resolve_resident("RESIDENT_999")


def test_alias_from_another_request_cannot_resolve():
    request_a = AliasContext()
    request_b = AliasContext()

    source = make_source()

    alias = request_a.alias_source(source)

    with pytest.raises(UnknownAliasError):
        request_b.resolve_source(alias)

def test_same_alias_string_is_scoped_to_its_own_request():
    request_a = AliasContext()
    request_b = AliasContext()

    source_a = make_source(
        source_type="mobility_observations",
    )

    source_b = make_source(
        source_type="falls_incidents",
    )

    alias_a = request_a.alias_source(source_a)
    alias_b = request_b.alias_source(source_b)

    # Both requests can independently use the same provider-facing label.
    assert alias_a == "SRC_001"
    assert alias_b == "SRC_001"

    # But SRC_001 has meaning only within its own request.
    assert request_a.resolve_source("SRC_001") == source_a
    assert request_b.resolve_source("SRC_001") == source_b