import asyncio

from intelligence.workers.celery_app import celery_app
from intelligence.workers.scheduling import run_schedule_sweep


@celery_app.task(name="intelligence.handover.schedule", ignore_result=True)
def schedule_handovers():
    asyncio.run(run_schedule_sweep())
