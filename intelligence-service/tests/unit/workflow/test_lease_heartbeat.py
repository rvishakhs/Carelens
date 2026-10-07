import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import SecretStr

from sqlalchemy.exc import SQLAlchemyError

from intelligence.workflow.failure_handling import record_execution_failure
from intelligence.handover.contracts import GenerationMetadata, ValidatedHandoverContent
from intelligence.persistence.job_repository import ClaimedJob, JobExecutionSnapshot
from intelligence.workflow import resident_handover as workflow
from tests.support.handover import make_input


@pytest.fixture
def setup(monkeypatch):
    value = make_input()
    expiry = datetime.now(UTC) + timedelta(seconds=60)
    claim = ClaimedJob(value.job_id, value.execution_context.tenant_id, uuid4(), expiry)
    snapshot = JobExecutionSnapshot(
        job_id=value.job_id, tenant_id=claim.tenant_id, resident_id=value.resident_id,
        initiating_actor_id=None, service_identity="test-worker", trigger="scheduled",
        purpose="handover_generation", shift_start=value.period.start,
        shift_end=value.period.end, timezone=value.care_home_timezone,
    )
    db = SimpleNamespace(close=AsyncMock())
    monkeypatch.setattr(workflow, "DatabaseSettings", lambda: SimpleNamespace(database_url=SecretStr("unused")))
    monkeypatch.setattr(workflow, "Database", lambda **kwargs: db)
    monkeypatch.setattr(workflow, "HEARTBEAT_INTERVAL_SECONDS", 0.001)
    monkeypatch.setattr(workflow, "RENEWAL_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(workflow, "reserve_handover_job", AsyncMock(return_value=claim))
    monkeypatch.setattr(workflow, "load_job_for_execution", AsyncMock(return_value=snapshot))
    # Exercise the real leave-unchanged branch; stub only database mutations.
    async def record(db, *, claim, decision):
        if decision.action == "leave":
            return await record_execution_failure(db, claim=claim, decision=decision)
        return "queued" if decision.action == "retry" else "failed"
    monkeypatch.setattr(workflow, "record_execution_failure", AsyncMock(side_effect=record))
    monkeypatch.setattr(workflow, "retrieve_shift_observations", AsyncMock(return_value=value.retrieval.evidence))
    renew = AsyncMock(return_value=expiry)
    save = AsyncMock(return_value=uuid4())
    monkeypatch.setattr(workflow, "renew_execution_lease", renew)
    monkeypatch.setattr(workflow, "save_original_and_complete_job", save)
    content = ValidatedHandoverContent(sections=(), coverage_complete=False)
    agent = SimpleNamespace(generate=AsyncMock(return_value=content))
    args = dict(
        tenant_id=claim.tenant_id, job_id=claim.job_id,
        authorizer=SimpleNamespace(authorise=AsyncMock(return_value=value.execution_context)),
        client=object(), access_token=SecretStr("synthetic"), handover_agent=agent,
        generation_metadata=GenerationMetadata(
            agent_version="test", prompt_version="test", gateway_version="test",
            provider="fake", model_version="test", generated_at=datetime.now(UTC),
        ),
    )
    return args, renew, save, db, content, expiry


def test_renews_during_generation_and_stops_before_save(setup):
    args, renew, save, db, content, expiry = setup

    async def run():
        renewed = asyncio.Event()

        async def renewal(*a, **kw):
            if renew.await_count >= 3:
                renewed.set()
            return expiry

        async def generate(**kw):
            await renewed.wait()
            return content

        async def saving(**kw):
            before = renew.await_count
            await asyncio.sleep(0.01)
            assert renew.await_count == before
            return uuid4()

        renew.side_effect = renewal
        args["handover_agent"].generate.side_effect = generate
        save.side_effect = saving
        result = await asyncio.wait_for(workflow.run_resident_handover_workflow(**args), 1)
        assert result["state"] == "draft_ready"
        assert renew.await_count >= 4  # Initial, multiple periodic, final.
        db.close.assert_awaited_once()
    asyncio.run(run())


@pytest.mark.parametrize("failure", ["lost", "database", "timeout"])
def test_failed_renewal_cancels_generation_and_prevents_save(setup, failure):
    args, renew, save, db, content, expiry = setup

    async def run():
        cancelled = asyncio.Event()

        async def generate(**kw):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        async def renewal(*a, **kw):
            if renew.await_count == 1:
                return expiry
            if failure == "lost":
                return None
            if failure == "database":
                raise SQLAlchemyError("unavailable")
            await asyncio.Event().wait()

        args["handover_agent"].generate.side_effect = generate
        renew.side_effect = renewal
        with pytest.raises(RuntimeError):
            await asyncio.wait_for(workflow.run_resident_handover_workflow(**args), 1)
        assert cancelled.is_set()
        decision = workflow.record_execution_failure.call_args.kwargs["decision"]
        assert decision.action == "leave"
        assert decision.code == ("lease_lost" if failure == "lost" else "lease_uncertain")
        save.assert_not_awaited()
        db.close.assert_awaited_once()
        before = renew.await_count
        await asyncio.sleep(0.01)
        assert renew.await_count == before
    asyncio.run(run())


def test_generation_failure_stops_renewal(setup):
    args, renew, save, db, content, expiry = setup
    args["handover_agent"].generate.side_effect = ValueError("invalid output")

    async def run():
        with pytest.raises(RuntimeError):
            await workflow.run_resident_handover_workflow(**args)
        before = renew.await_count
        await asyncio.sleep(0.01)
        assert renew.await_count == before
        save.assert_not_awaited()
        db.close.assert_awaited_once()
    asyncio.run(run())


def test_worker_cancellation_stops_renewal(setup):
    args, renew, save, db, content, expiry = setup

    async def run():
        started = asyncio.Event()

        async def generate(**kw):
            started.set()
            await asyncio.Event().wait()

        args["handover_agent"].generate.side_effect = generate
        task = asyncio.create_task(workflow.run_resident_handover_workflow(**args))
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        before = renew.await_count
        await asyncio.sleep(0.01)
        assert renew.await_count == before
        save.assert_not_awaited()
        db.close.assert_awaited_once()
    asyncio.run(run())


def test_final_renewal_refusal_prevents_save(setup):
    args, renew, save, db, content, expiry = setup
    renew.side_effect = [expiry, None]
    with pytest.raises(RuntimeError, match="lease_lost"):
        asyncio.run(workflow.run_resident_handover_workflow(**args))
    save.assert_not_awaited()
    db.close.assert_awaited_once()


@pytest.mark.parametrize("phase", ["initial", "final"])
@pytest.mark.parametrize("failure", ["database", "timeout"])
def test_renewal_uncertainty_at_workflow_boundaries(setup, phase, failure):
    args, renew, save, db, content, expiry = setup

    async def renewal(*a, **kw):
        if phase == "final" and renew.await_count == 1:
            return expiry
        if failure == "database":
            raise SQLAlchemyError("unavailable")
        await asyncio.Event().wait()

    renew.side_effect = renewal
    with pytest.raises(RuntimeError, match="unchanged:lease_uncertain"):
        asyncio.run(workflow.run_resident_handover_workflow(**args))
    save.assert_not_awaited()
    if phase == "initial":
        args["handover_agent"].generate.assert_not_awaited()
    else:
        args["handover_agent"].generate.assert_awaited_once()
    db.close.assert_awaited_once()
