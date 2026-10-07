import asyncio

from intelligence.workers.celery_app import celery_app
from intelligence.workers.recovery import run_recovery_sweep


@celery_app.task(
    name="intelligence.handover.recover",
    ignore_result=True,
)
def recover_handover_jobs() -> None:
    asyncio.run(run_recovery_sweep())