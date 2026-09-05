from app.shared.celery import celery_app


@celery_app.task
def test_task(name: str) -> str:
    return f"test_task with name {name}"

