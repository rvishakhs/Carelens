"""HTTP contract checks with controlled probes; no live infrastructure needed."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

import app.main as application


async def _get(path: str):
    # ASGITransport does not run lifespan: probes are replaced by each test.
    async with AsyncClient(transport=ASGITransport(app=application.app), base_url="http://test") as client:
        return await client.get(path)


@pytest.mark.parametrize("database_ok,redis_ok", [(True, True), (False, True), (True, False), (False, False)])
async def test_readiness_reports_awaited_dependency_results(monkeypatch, database_ok, redis_ok):
    database = AsyncMock(return_value=database_ok)
    redis = AsyncMock(return_value=redis_ok)
    monkeypatch.setattr(application, "check_database", database)
    monkeypatch.setattr(application, "check_redis", redis)

    response = await _get("/readyz")

    assert response.status_code == (200 if database_ok and redis_ok else 503)
    assert response.json() == {
        "status": "ready" if database_ok and redis_ok else "not_ready",
        "dependencies": {
            "Redis": "available" if redis_ok else "unavailable",
            "Database": "available" if database_ok else "unavailable",
        },
    }
    database.assert_awaited_once_with()
    redis.assert_awaited_once_with()


@pytest.mark.parametrize("failed", ["Database", "Redis"])
async def test_readiness_reports_probe_exceptions_as_unavailable(monkeypatch, failed):
    database = AsyncMock(return_value=True)
    redis = AsyncMock(return_value=True)
    probes = {"Database": database, "Redis": redis}
    probes[failed].side_effect = RuntimeError("Dependency not initialised")
    monkeypatch.setattr(application, "check_database", database)
    monkeypatch.setattr(application, "check_redis", redis)

    response = await _get("/readyz")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["dependencies"][failed] == "unavailable"
    assert response.json()["dependencies"]["Redis" if failed == "Database" else "Database"] == "available"
    assert "Dependency not initialised" not in response.text
    database.assert_awaited_once_with()
    redis.assert_awaited_once_with()


@pytest.mark.parametrize("failed", ["Database", "Redis"])
async def test_readiness_times_out_and_cancels_a_stalled_probe(monkeypatch, failed):
    cancelled = asyncio.Event()

    async def stalled():
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(application, "READINESS_TIMEOUT_SECONDS", 0.02)
    healthy = AsyncMock(return_value=True)
    monkeypatch.setattr(application, "check_database", stalled if failed == "Database" else healthy)
    monkeypatch.setattr(application, "check_redis", stalled if failed == "Redis" else healthy)

    response = await asyncio.wait_for(_get("/readyz"), timeout=1)

    assert response.status_code == 503
    assert response.json()["dependencies"][failed] == "unavailable"
    assert response.json()["dependencies"]["Redis" if failed == "Database" else "Database"] == "available"
    assert cancelled.is_set()
    healthy.assert_awaited_once_with()


async def test_readiness_starts_probes_concurrently(monkeypatch):
    database_started = asyncio.Event()
    redis_started = asyncio.Event()

    async def database():
        database_started.set()
        await redis_started.wait()
        return True

    async def redis():
        redis_started.set()
        await database_started.wait()
        return True

    monkeypatch.setattr(application, "check_database", database)
    monkeypatch.setattr(application, "check_redis", redis)

    response = await asyncio.wait_for(_get("/readyz"), timeout=1)

    assert response.status_code == 200


async def test_liveness_does_not_probe_dependencies(monkeypatch):
    database = AsyncMock(side_effect=RuntimeError("Database unavailable"))
    redis = AsyncMock(side_effect=RuntimeError("Redis unavailable"))
    monkeypatch.setattr(application, "check_database", database)
    monkeypatch.setattr(application, "check_redis", redis)

    response = await _get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    database.assert_not_called()
    redis.assert_not_called()
