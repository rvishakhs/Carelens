from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from intelligence.core.contracts import Scope


def fixture():
    tenant, resident, actor = uuid4(), uuid4(), uuid4()
    scope = Scope(
        tenant_id=tenant,
        actor_id=actor,
        resident_ids=frozenset({resident}),
        permissions=frozenset({"handover:generate"}),
    )
    now = datetime.now(UTC)
    job = SimpleNamespace(
        id=uuid4(),
        tenant_id=tenant,
        resident_id=resident,
        state="draft_ready",
        shift_start=now,
        shift_end=now,
    )
    original = SimpleNamespace(
        id=uuid4(),
        manifest_id=uuid4(),
        version_number=1,
        version_kind="ai_original",
        authored_by=None,
        previous_version_id=None,
        sections=[{"category": "care_delivered", "claims": [{"text": "Recorded care", "sources": []}]}],
        warnings=[{"message": "Partial coverage"}],
        created_at=now,
        generated_at=now,
        agent_version="test",
        prompt_version="test",
        gateway_version="test",
        provider="openai",
        model_version="test",
    )
    return scope, job, original


def database(*results):
    session = SimpleNamespace(
        scalar=AsyncMock(side_effect=results), execute=AsyncMock(), flush=AsyncMock(), add=Mock()
    )

    @asynccontextmanager
    async def begin():
        yield

    @asynccontextmanager
    async def connect():
        yield session

    session.begin = begin
    return SimpleNamespace(session=connect), session


