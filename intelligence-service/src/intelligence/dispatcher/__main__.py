"""Run with python -m intelligence.dispatcher alongside the API and Celery worker."""

import asyncio
import logging
import signal

from intelligence.config import DatabaseSettings, DispatcherSettings, WorkerSettings
from intelligence.dispatcher.publisher import CeleryPublisher
from intelligence.dispatcher.service import dispatch_once
from intelligence.persistence.database import Database
from intelligence.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def run() -> None:
    settings = DispatcherSettings()
    worker = WorkerSettings()
    db = Database(DatabaseSettings().database_url.get_secret_value())
    publisher = CeleryPublisher(celery_app, queue=worker.handover_queue)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    try:
        while not stop.is_set():
            attempted = False
            for tenant_id in dict.fromkeys(settings.tenant_ids):
                if stop.is_set():
                    break
                try:
                    # Bound database outages as well as publication. An abandoned
                    # reservation becomes eligible after its lease expires.
                    async with asyncio.timeout(30):
                        attempted |= await dispatch_once(db, tenant_id=tenant_id, publisher=publisher)
                except Exception:
                    logger.error("outbox_dispatch_unavailable")
            try:
                await asyncio.wait_for(stop.wait(), timeout=0.05 if attempted else settings.poll_seconds)
            except TimeoutError:
                pass
    finally:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.remove_signal_handler(sig)
        await db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
