import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from celery import Celery

from intelligence.dispatcher import service
from intelligence.dispatcher.publisher import CeleryPublisher
from intelligence.persistence.outbox_repository import ClaimedDispatch


@pytest.fixture
def claim():
    return ClaimedDispatch(
        uuid4(),
        uuid4(),
        uuid4(),
        "intelligence.handover.generate",
        uuid4(),
        datetime.now(UTC) + timedelta(seconds=60),
        attempts=2,
    )


@pytest.fixture
def setup(monkeypatch, claim):
    session = MagicMock()
    session.execute = AsyncMock()
    active = []

    @asynccontextmanager
    async def begin():
        active.append(True)
        try:
            yield
        finally:
            active.pop()

    @asynccontextmanager
    async def get_session():
        yield session

    session.begin = begin
    db = SimpleNamespace(session=get_session)
    reserve = AsyncMock(return_value=claim)
    finish = AsyncMock(return_value=True)
    monkeypatch.setattr(service, "reserve_next_dispatch", reserve)
    monkeypatch.setattr(service, "finish_dispatch", finish)
    publisher = SimpleNamespace(publish=AsyncMock())
    return db, publisher, reserve, finish, active


def test_success_records_publication_after_sending(setup, claim):
    db, publisher, reserve, finish, active = setup

    async def publish(received):
        assert received == claim and not active
        finish.assert_not_awaited()

    async def record(*args, **kwargs):
        assert active and kwargs["published"] is True
        return True

    publisher.publish.side_effect = publish
    finish.side_effect = record
    assert asyncio.run(service.dispatch_once(db, tenant_id=claim.tenant_id, publisher=publisher))
    finish.assert_awaited_once()


def test_empty_outbox_does_not_publish(setup, claim):
    db, publisher, reserve, finish, _ = setup
    reserve.return_value = None
    assert not asyncio.run(service.dispatch_once(db, tenant_id=claim.tenant_id, publisher=publisher))
    publisher.publish.assert_not_awaited()
    finish.assert_not_awaited()


def test_uncertain_publish_is_retried_without_logging_credentials(setup, claim, caplog):
    db, publisher, reserve, finish, _ = setup
    publisher.publish.side_effect = RuntimeError("redis://secret-password@broker")
    asyncio.run(service.dispatch_once(db, tenant_id=claim.tenant_id, publisher=publisher))
    kwargs = finish.call_args.kwargs
    assert kwargs["published"] is False
    assert 8 <= kwargs["retry_seconds"] <= 12
    assert "secret-password" not in caplog.text


def test_bookkeeping_failure_propagates_for_lease_recovery(setup, claim):
    db, publisher, reserve, finish, _ = setup
    finish.side_effect = RuntimeError("database unavailable")
    with pytest.raises(RuntimeError):
        asyncio.run(service.dispatch_once(db, tenant_id=claim.tenant_id, publisher=publisher))
    publisher.publish.assert_awaited_once_with(claim)
    assert finish.call_args.kwargs["published"] is True


def test_cancellation_leaves_reservation_for_recovery(setup, claim):
    db, publisher, reserve, finish, _ = setup
    publisher.publish.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(service.dispatch_once(db, tenant_id=claim.tenant_id, publisher=publisher))
    finish.assert_not_awaited()


def test_stale_dispatcher_does_not_claim_delivery(setup, claim, caplog):
    db, publisher, reserve, finish, _ = setup
    finish.return_value = False
    asyncio.run(service.dispatch_once(db, tenant_id=claim.tenant_id, publisher=publisher))
    assert "outbox_lease_lost" in caplog.text


def test_celery_payload_and_retry_options(claim):
    app = MagicMock()
    publisher = CeleryPublisher(app, queue="intelligence.handover")
    asyncio.run(publisher.publish(claim))
    options = app.send_task.call_args.kwargs
    assert app.send_task.call_args.args == ("intelligence.handover.generate",)
    assert options["kwargs"] == {"tenant_id": str(claim.tenant_id), "job_id": str(claim.job_id)}
    assert options["task_id"] == str(claim.outbox_id)
    assert options["retry"] is False
    assert options["queue"] == "intelligence.handover"
    assert options["serializer"] == "json"


def test_actual_celery_publication_with_in_memory_transport(claim):
    queue_name = f"test-outbox-{uuid4()}"
    app = Celery("test-dispatch", broker="memory://")
    try:
        asyncio.run(CeleryPublisher(app, queue=queue_name).publish(claim))
        with app.connection_for_read() as connection:
            with connection.SimpleQueue(queue_name) as queue:
                message = queue.get(block=False)
                assert message.headers["task"] == "intelligence.handover.generate"
                assert message.headers["id"] == str(claim.outbox_id)
                assert message.payload[1] == {
                    "tenant_id": str(claim.tenant_id),
                    "job_id": str(claim.job_id),
                }
                message.ack()
    finally:
        app.close()
