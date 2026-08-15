from fastapi import FastAPI

from app.container import Container
from app.modules.residents.router import care_plans_router, router


def register(app: FastAPI, container: Container) -> None:
    app.include_router(router)
    app.include_router(care_plans_router)
