"""Opt-in PostgreSQL transaction tests; all records rolled back by the harness."""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text, update

from intelligence.dispatcher.service import dispatch_once, reserve_next_dispatch
from intelligence.persistence.models import DispatchOutbox, HandoverJob
from intelligence.persistence.outbox_repository import finish_dispatch
from tests.support.database import submission_harness

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("INTELLIGENCE_RUN_DB_TESTS") != "1",
        reason="Requires opted-in local PostgreSQL",
    ),
]


@asynccontextmanager
async def scoped(h):
    async with h.database.session() as session, session.begin():
        await session.execute(
            text("SELECT set_config('intelligence.tenant_id', :tenant, true)"),
            {"tenant": str(h.scope.tenant_id)},
        )
        yield session


async def make_due(h, *, expire=False):
    async with scoped(h) as session:
        values = {"available_at": func.clock_timestamp() - timedelta(seconds=1)}
        if expire:
            values["lease_expires_at"] = func.clock_timestamp() - timedelta(seconds=1)
        await session.execute(
            update(DispatchOutbox)
            .where(
                DispatchOutbox.tenant_id == h.scope.tenant_id,
            )
            .values(**values)
        )


def test_publish_records_delivery_once():
    async def run():
        async with submission_harness() as h:
            await h.submit()
            publisher = AsyncMock()
            assert await dispatch_once(h.database, tenant_id=h.scope.tenant_id, publisher=publisher)
            assert not await dispatch_once(h.database, tenant_id=h.scope.tenant_id, publisher=publisher)
            assert publisher.publish.await_count == 1
            async with scoped(h) as session:
                row = await session.scalar(
                    select(DispatchOutbox).where(DispatchOutbox.tenant_id == h.scope.tenant_id)
                )
                assert row.state == "published" and row.published_at is not None
                assert row.lease_token is None and row.failure_code is None

    asyncio.run(run())


def test_ambiguous_publish_requeues_with_backoff_then_recovers():
    async def run():
        async with submission_harness() as h:
            await h.submit()
            publisher = AsyncMock()
            publisher.publish.side_effect = RuntimeError("delivery response lost")
            await dispatch_once(h.database, tenant_id=h.scope.tenant_id, publisher=publisher)
            assert await reserve_next_dispatch(h.database, tenant_id=h.scope.tenant_id) is None
            async with scoped(h) as session:
                row = await session.scalar(
                    select(DispatchOutbox).where(DispatchOutbox.tenant_id == h.scope.tenant_id)
                )
                assert row.state == "pending" and row.failure_code == "publish_unconfirmed"
                assert row.lease_token is None and row.attempts == 1
            await make_due(h)
            publisher.publish.side_effect = None
            await dispatch_once(h.database, tenant_id=h.scope.tenant_id, publisher=publisher)
            assert publisher.publish.await_count == 2

    asyncio.run(run())


def test_crashed_dispatcher_reclaimed_and_old_token_fenced():
    async def run():
        async with submission_harness() as h:
            await h.submit()
            old = await reserve_next_dispatch(h.database, tenant_id=h.scope.tenant_id)
            assert old is not None
            assert await reserve_next_dispatch(h.database, tenant_id=h.scope.tenant_id) is None
            await make_due(h, expire=True)
            current = await reserve_next_dispatch(h.database, tenant_id=h.scope.tenant_id)
            assert current is not None and current.lease_token != old.lease_token
            assert current.attempts == 2 and current.outbox_id == old.outbox_id
            async with scoped(h) as session:
                assert not await finish_dispatch(session, claim=old, published=True)
                assert await finish_dispatch(session, claim=current, published=True)

    asyncio.run(run())


def test_future_job_and_other_tenant_are_not_dispatched():
    async def run():
        async with submission_harness() as h:
            await h.submit()
            assert await reserve_next_dispatch(h.database, tenant_id=uuid4()) is None
            async with scoped(h) as session:
                await session.execute(
                    update(HandoverJob)
                    .where(HandoverJob.tenant_id == h.scope.tenant_id)
                    .values(
                        next_attempt_at=func.clock_timestamp() + timedelta(minutes=5),
                    )
                )
            assert await reserve_next_dispatch(h.database, tenant_id=h.scope.tenant_id) is None

    asyncio.run(run())
