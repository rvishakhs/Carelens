from intelligence.workers.celery_app import celery_app


@celery_app.task(
    name="intelligence.handover.check",
    ignore_result=True,
)
def check_handover_worker() -> None:
    print("Handover worker received the task")