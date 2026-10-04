import asyncio
from uuid import UUID

from intelligence.workers.celery_app import celery_app
from intelligence.workflow.resident_handover import (
    run_resident_handover_workflow,
)


# @celery_app.task(
#     name="intelligence.handover.check",
#     ignore_result=True,
# )
# def check_handover_worker() -> None:
#     print("Handover worker received the task")
#
#

@celery_app.task(
    name="intelligence.handover.generate",
    ignore_result=True,
)
def generate_resident_handover(
    tenant_id: str,
    job_id: str,
) -> None:
    asyncio.run(
        run_resident_handover_workflow(
            tenant_id=UUID(tenant_id),
            job_id=UUID(job_id),
        )
    )