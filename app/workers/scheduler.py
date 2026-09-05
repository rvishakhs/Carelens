"""APScheduler wiring for the nightly (07:00) and shift-end cron jobs. Runs as a
separate process from the API (`python -m workers.scheduler`), sharing the same
Container construction as app.main so both speak through identical ports."""

import asyncio
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.container import Container, build_container
from app.shared.database import init_engine
from app.shared.telemetry import configure_logging, get_logger
from app.workers.jobs.retention_job import run_retention_job
from app.workers.jobs.summary_job import run_summary_job

logger = get_logger(__name__)


def _enabled_care_home_ids() -> list[uuid.UUID]:
    # TODO: replace with a real tenant registry query once one exists -- see
    # workers/jobs/summary_job.py's docstring for why there isn't one in Phase 1.
    return []


async def _summary_tick(container: Container) -> None:
    await run_summary_job(container, _enabled_care_home_ids())


async def _retention_tick(container: Container) -> None:
    await run_retention_job(container, _enabled_care_home_ids())


def build_scheduler() -> AsyncIOScheduler:
    settings = get_settings()
    configure_logging(settings.log_level, json_output=not settings.debug)
    init_engine(settings.database_url, pool_size=settings.db_pool_size)
    container = build_container(settings)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(_summary_tick, CronTrigger(hour=7, minute=0), args=[container], id="daily_summary_0700")
    scheduler.add_job(_summary_tick, CronTrigger(hour=19, minute=0), args=[container], id="daily_summary_shift_end")
    scheduler.add_job(_retention_tick, CronTrigger(hour=3, minute=0), args=[container], id="retention_sweep_0300")
    return scheduler


def main() -> None:
    scheduler = build_scheduler()
    scheduler.start()
    logger.info("scheduler_started")
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
