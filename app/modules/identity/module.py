from fastapi import FastAPI

from app import Container
from app.modules.identity.router import router


def register(app: FastAPI, container: Container) -> None:
    app.include_router(router)