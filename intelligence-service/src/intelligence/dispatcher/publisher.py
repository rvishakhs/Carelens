"""At-least-once Celery publication. Task IDs aid tracing, not deduplication."""

import asyncio

from celery import Celery

from intelligence.persistence.outbox_repository import ClaimedDispatch


class CeleryPublisher:
    def __init__(self, app: Celery, *, queue: str) -> None:
        self._app = app
        self._queue = queue

    async def publish(self, claim: ClaimedDispatch) -> None:
        if claim.task_name != "intelligence.handover.generate":
            raise ValueError("Unsupported outbox task")
        # Celery's producer is synchronous; keep DB/event-loop work responsive.
        await asyncio.to_thread(self._send, claim)

    def _send(self, claim: ClaimedDispatch) -> None:
        with self._app.connection_for_write(
            connect_timeout=5,
            transport_options={
                "socket_connect_timeout": 5,
                "socket_timeout": 5,
                "retry_on_timeout": False,
                "max_retries": 0,
            },
        ) as connection:
            self._app.send_task(
                "intelligence.handover.generate",
                kwargs={"tenant_id": str(claim.tenant_id), "job_id": str(claim.job_id)},
                task_id=str(claim.outbox_id),
                queue=self._queue,
                serializer="json",
                delivery_mode=2,
                ignore_result=True,
                retry=False,
                connection=connection,
            )
