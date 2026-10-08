import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx

from intelligence.workers import handover_execution as worker


def test_worker_builds_dependencies_and_closes_clients(monkeypatch):
    monkeypatch.setenv("INTELLIGENCE_TOKEN_URL", "https://identity.test/token")
    monkeypatch.setenv("INTELLIGENCE_CLIENT_ID", "worker")
    monkeypatch.setenv("INTELLIGENCE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("INTELLIGENCE_SERVICE_IDENTITY", "intelligence-api")
    monkeypatch.setenv("CARELENS_BASE_URL", "https://carelens.test")

    @asynccontextmanager
    async def providers():
        yield SimpleNamespace(
            handover=object(),
            provider="openai",
            model="test-model",
            prompt_version="openai-extractive-v1",
            timeout_seconds=25,
        )

    monkeypatch.setattr(worker, "open_provider_runtime", providers)
    tenant, job = uuid4(), uuid4()
    clients = []
    actual_client = httpx.AsyncClient

    def handler(request):
        assert request.url == "https://identity.test/token"
        return httpx.Response(
            200, json={"access_token": "worker-token", "token_type": "Bearer", "expires_in": 300}
        )

    def factory(**kwargs):
        client = actual_client(**kwargs, transport=httpx.MockTransport(handler))
        clients.append(client)
        return client

    workflow = AsyncMock(return_value={"state": "draft_ready"})
    monkeypatch.setattr(worker.httpx, "AsyncClient", factory)
    monkeypatch.setattr(worker, "run_resident_handover_workflow", workflow)
    assert asyncio.run(worker.run_handover_task(tenant_id=tenant, job_id=job)) == {"state": "draft_ready"}
    kwargs = workflow.call_args.kwargs
    assert kwargs["tenant_id"] == tenant and kwargs["job_id"] == job
    assert kwargs["access_token"].get_secret_value() == "worker-token"
    assert kwargs["client"]._service_tenant_id == tenant
    assert kwargs["generation_metadata"].provider == "openai"
    assert kwargs["authorizer"]._identity == "intelligence-api"
    assert len(clients) == 3 and all(client.is_closed for client in clients)


def test_celery_task_calls_setup_with_only_ids(monkeypatch):
    monkeypatch.setenv("INTELLIGENCE_BROKER_URL", "redis://localhost:6379/15")
    from intelligence.tasks import handover

    setup = AsyncMock()
    monkeypatch.setattr(handover, "run_handover_task", setup)
    tenant, job = uuid4(), uuid4()
    handover.generate_resident_handover.run(str(tenant), str(job))
    setup.assert_awaited_once_with(tenant_id=tenant, job_id=job)
