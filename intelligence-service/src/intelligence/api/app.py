import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from secrets import compare_digest
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text

from intelligence.agents.base import AgentContext
from intelligence.agents.registry import default_registry
from intelligence.config import Settings
from intelligence.connectors.synthetic import (
    SyntheticEvidenceReader,
    demo_scope,
)
from intelligence.core.contracts import RunRequest, RunResult, Scope
from intelligence.core.errors import (
    AccessDenied,
    CapacityExceeded,
    GatewayRejected,
)
from intelligence.core.results import MemoryResults
from intelligence.gateway.fake import FakeProvider
from intelligence.gateway.service import Gateway
from intelligence.persistence.database import Database
from intelligence.api.dependencies import actor
from intelligence.api.handover import router as handover_router

logger = logging.getLogger(__name__)

DATABASE_CHECK_TIMEOUT_SECONDS = 5


async def check_database(database: Database) -> None:
    """Verify that PostgreSQL responds within a bounded time."""
    async with asyncio.timeout(DATABASE_CHECK_TIMEOUT_SECONDS):
        async with database.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else Settings()  # type: ignore[call-arg]

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = Database(database_url=config.database_url.get_secret_value())

        try:
            await check_database(database)
            app.state.database = database
            logger.info("Database connection verified")

            # FastAPI starts serving requests here.
            yield

        finally:
            # Also runs if the startup database check fails.
            await database.close()
            logger.info("Database connection pool disposed")

    app = FastAPI(
        title="Independent Care Intelligence — synthetic skeleton",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.state.settings = config

    registry = default_registry()

    context = AgentContext(
        reader=SyntheticEvidenceReader(),
        gateway=Gateway(FakeProvider()),
    )

    results = MemoryResults(
        config.result_ttl_seconds,
        config.max_results,
    )

    app.include_router(handover_router)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(
        _: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        # Avoid returning potentially sensitive input values.
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {
                        "type": error["type"],
                        "loc": list(error["loc"]),
                    }
                    for error in exc.errors()
                ]
            },
        )

    @app.get("/healthz")
    async def health() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/readyz")
    async def ready(request: Request) -> JSONResponse:
        database: Database | None = getattr(
            request.app.state,
            "database",
            None,
        )

        database_available = False

        if database is not None:
            try:
                await check_database(database)
                database_available = True
            except Exception:
                # Do not expose connection details or raw exceptions.
                logger.warning("Database readiness check failed")

        return JSONResponse(
            status_code=200 if database_available else 503,
            content={
                "status": "ready" if database_available else "not_ready",
                "database": ("available" if database_available else "unavailable"),
                "mode": "synthetic",
                "provider": "fake",
                "durable": False,
                "live_carelens_connected": False,
            },
        )

    @app.get("/v1/agents")
    async def agents(
        _: Scope = Depends(actor),
    ) -> list[dict[str, str]]:
        return registry.describe()

    @app.post("/v1/runs", response_model=RunResult)
    async def run(
        payload: RunRequest,
        scope: Scope = Depends(actor),
    ) -> RunResult:
        try:
            agent = registry.get(payload.agent_id)
            result = await agent.run(scope, payload, context)

            results.put(scope, result, agent.permission)

            return result

        except AccessDenied:
            raise HTTPException(
                status_code=404,
                detail="Resource unavailable",
            ) from None

        except GatewayRejected:
            raise HTTPException(
                status_code=502,
                detail="Gateway rejected provider output",
            ) from None

        except CapacityExceeded:
            raise HTTPException(
                status_code=503,
                detail="Demo result capacity reached; retry after expiry",
            ) from None

    @app.get("/v1/runs/{run_id}", response_model=RunResult)
    async def get_run(
        run_id: UUID,
        scope: Scope = Depends(actor),
    ) -> RunResult:
        result = results.get(scope, run_id)

        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Resource unavailable",
            )

        return result

    return app
