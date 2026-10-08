from celery import Celery

from intelligence.config import WorkerSettings


settings = WorkerSettings()

celery_app = Celery(
    "intelligence",
    broker=settings.broker_url.get_secret_value(),
    include=["intelligence.tasks.handover",
             "intelligence.tasks.recovery", "intelligence.tasks.scheduling"
             ]
)

celery_app.conf.update(
    # Accept JSON task messages only.
    task_serializer="json",
    accept_content=["json"],

    task_routes={
        "intelligence.handover.schedule": {"queue": "intelligence.scheduling"},
        "intelligence.handover.recover": {
            "queue": "intelligence.maintenance",
        },
    },

    beat_schedule={
        "submit-completed-handovers": {
            "task": "intelligence.handover.schedule",
            "schedule": 60.0,
            "options": {"queue": "intelligence.scheduling", "expires": 60},
        },
        "recover-expired-handovers": {
            "task": "intelligence.handover.recover",
            "schedule": 30.0,
            "options": {
                "queue": "intelligence.maintenance",
                "expires": 30,
            },
        },
    },

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
