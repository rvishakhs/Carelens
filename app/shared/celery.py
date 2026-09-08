from celery import Celery
from kombu import Queue

from app import get_settings

settings = get_settings()

celery_app = Celery(
    "carelens",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.task_queues = (
    Queue("carelens.default"),
    Queue("carelens.notifications"),
    Queue("carelens.documents"),
    Queue("carelens.ai"),
)

##### Auto Discovery of tasks #####
# celery_app.autodiscover_tasks([
#     "app.workers.tasks"
# ])


##### Manual Discovery of tasks #####
celery_app.conf.imports = (
    "app.workers.tasks.task1",
)