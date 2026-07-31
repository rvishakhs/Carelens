"""FastAPI app factory. Wires modules from config -- removing a module from
ENABLED_MODULES removes its routes, jobs, and event handlers with zero code
changes elsewhere."""

from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.container import Container, build_container
from app.shared.database import init_engine
from app.shared.exceptions import CareLensError
from app.shared.telemetry import configure_logging, get_logger

logger = get_logger(__name__)

ModuleRegistrar = Callable[[FastAPI, Container], None]


def _load_module_registry() -> dict[str, ModuleRegistrar]:
    from app.modules.ai_gateway.module import register as register_ai_gateway
    from app.modules.ai_insights.module import register as register_ai_insights
    from app.modules.audit.module import register as register_audit
    from app.modules.care_recording.module import register as register_care_recording
    from app.modules.floors.module import register as register_floors
    from app.modules.handover.module import register as register_handover
    from app.modules.identity.module import register as register_identity
    from app.modules.medications.module import register as register_medications
    from app.modules.observations.module import register as register_observations
    from app.modules.residents.module import register as register_residents
    from app.modules.summaries.module import register as register_summaries

    return {
        "identity": register_identity,
        "residents": register_residents,
        "floors": register_floors,
        "observations": register_observations,
        "medications": register_medications,
        "care_recording": register_care_recording,
        "audit": register_audit,
        "ai_gateway": register_ai_gateway,
        "summaries": register_summaries,
        "ai_insights": register_ai_insights,
        "handover": register_handover,
    }


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, json_output=not settings.debug)

    app = FastAPI(title=settings.app_name, debug=settings.debug)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(CareLensError)
    async def handle_carelens_error(request: Request, exc: CareLensError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "message": exc.message})

    init_engine(settings.database_url, pool_size=settings.db_pool_size)
    container = build_container(settings)
    app.state.container = container

    registry = _load_module_registry()
    for module_name in settings.enabled_modules_list:
        register = registry.get(module_name)
        if register is None:
            raise RuntimeError(f"Unknown module in ENABLED_MODULES: {module_name!r}")
        register(app, container)
        logger.info("module_registered", module=module_name)

    @app.get("/healthz", tags=["system"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", tags=["system"])
    async def readyz() -> dict[str, str]:
        # TODO: check DB + redis connectivity once pool wiring lands.
        return {"status": "ready"}

    return app


app = create_app()