from celery import Celery

from intelligence.config import WorkerSettings


settings = WorkerSettings()

celery_app = Celery(
    "intelligence",
    broker=settings.broker_url.get_secret_value(),
    include=["intelligence.tasks.handover"],
)

celery_app.conf.update(
    # Accept JSON task messages only.
    task_serializer="json",
    accept_content=["json"],

    # Default destination for tasks without an explicit route.
    task_default_queue=settings.handover_queue,

    # PostgreSQL holds our job status and generated drafts.
    task_ignore_result=True,

    # Each worker process reserves one message at a time.
    worker_prefetch_multiplier=1,

    # Retry connecting if Redis is unavailable during startup.
    broker_connection_retry_on_startup=True,

    # Use UTC internally; local schedules will use this timezone.
    enable_utc=True,
    timezone="Europe/London",
)