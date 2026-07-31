from fastapi import FastAPI

from app.container import Container
from app.modules.ai_insights.router import router


def register(app: FastAPI, container: Container) -> None:
    app.include_router(router)
