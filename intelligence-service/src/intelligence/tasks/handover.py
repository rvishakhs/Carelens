import asyncio
from uuid import UUID

from intelligence.workers.celery_app import celery_app
from intelligence.workers.handover_execution import run_handover_task


@celery_app.task(
    name="intelligence.handover.generate",
    ignore_result=True,
)
def generate_resident_handover(
    tenant_id: str,
    job_id: str,
) -> None:
    asyncio.run(
        run_handover_task(
            tenant_id=UUID(tenant_id),
            job_id=UUID(job_id),
        )
    )
