from fastapi import FastAPI

from app.container import Container
from app.modules.handover.router import router


def register(app: FastAPI, container: Container) -> None:
    app.include_router(router)
