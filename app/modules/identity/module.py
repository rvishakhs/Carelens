from fastapi import FastAPI

from app import Container
from app.modules.identity.intelligence_router import router as intelligence_router
from app.modules.identity.router import router


def register(app: FastAPI, container: Container) -> None:
    app.include_router(router)
    app.include_router(intelligence_router)
