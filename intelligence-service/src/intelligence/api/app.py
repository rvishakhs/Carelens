from secrets import compare_digest
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from intelligence.agents.base import AgentContext
from intelligence.agents.registry import default_registry
from intelligence.config import Settings
from intelligence.connectors.synthetic import SyntheticEvidenceReader, demo_scope
from intelligence.core.contracts import RunRequest, RunResult, Scope
from intelligence.core.errors import AccessDenied, CapacityExceeded, GatewayRejected
from intelligence.core.results import MemoryResults
from intelligence.gateway.fake import FakeProvider
from intelligence.gateway.service import Gateway


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()  # type: ignore[call-arg]
    app = FastAPI(title="Independent Care Intelligence — synthetic skeleton", version="0.1.0")
    registry = default_registry()
    context = AgentContext(reader=SyntheticEvidenceReader(), gateway=Gateway(FakeProvider()))
    results = MemoryResults(config.result_ttl_seconds, config.max_results)
    bearer = HTTPBearer(auto_error=False)

    def actor(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Scope:
        if credentials is None or not compare_digest(
            credentials.credentials.encode(), config.demo_token.get_secret_value().encode()
        ):
            raise HTTPException(401, "Invalid demo credentials", headers={"WWW-Authenticate": "Bearer"})
        # Fixed server-owned synthetic identity. Never derive scope from request/model fields.
        return demo_scope()

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Default validation responses can echo sensitive input; expose field locations only.
        return JSONResponse(
            status_code=422,
            content={"detail": [{"type": e["type"], "loc": list(e["loc"])} for e in exc.errors()]},
        )

    @app.get("/healthz")
    async def health() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/readyz")
    async def ready() -> dict[str, object]:
        return {
            "status": "ready",
            "mode": "synthetic",
            "provider": "fake",
            "durable": False,
            "live_carelens_connected": False,
        }

    @app.get("/v1/agents")
    async def agents(_: Scope = Depends(actor)) -> list[dict[str, str]]:
        return registry.describe()

    @app.post("/v1/runs", response_model=RunResult)
    async def run(payload: RunRequest, scope: Scope = Depends(actor)) -> RunResult:
        try:
            agent = registry.get(payload.agent_id)
            result = await agent.run(scope, payload, context)
            results.put(scope, result, agent.permission)
            return result
        except AccessDenied:
            raise HTTPException(404, "Resource unavailable") from None
        except GatewayRejected:
            raise HTTPException(502, "Gateway rejected provider output") from None
        except CapacityExceeded:
            raise HTTPException(503, "Demo result capacity reached; retry after expiry") from None

    @app.get("/v1/runs/{run_id}", response_model=RunResult)
    async def get_run(run_id: UUID, scope: Scope = Depends(actor)) -> RunResult:
        result = results.get(scope, run_id)
        if result is None:
            raise HTTPException(404, "Resource unavailable")
        return result

    return app
