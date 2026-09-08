from fastapi import FastAPI

from app import Container
from app.modules.medications.router import router


def register(app: FastAPI, container: Container) -> None:
    app.include_router(router)
