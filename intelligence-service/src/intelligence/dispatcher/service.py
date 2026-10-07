import asyncio
import logging
import random
from typing import Protocol
from uuid import UUID

from sqlalchemy import text

from intelligence.persistence.database import Database
from intelligence.persistence.outbox_repository import (
    ClaimedDispatch,
    claim_pending_dispatch,
    finish_dispatch,
)

logger = logging.getLogger(__name__)


class Publisher(Protocol):
    async def publish(self, claim: ClaimedDispatch) -> None: ...


async def reserve_next_dispatch(
    db: Database,
    *,
    tenant_id: UUID,
) -> ClaimedDispatch | None:
    # tenant_id must come from trusted dispatcher configuration
    # or an authorised tenant registry.
    async with db.session() as session:
        async with session.begin():
            await session.execute(
                text("SELECT set_config('intelligence.tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )

            claim = await claim_pending_dispatch(
                session,
                tenant_id=tenant_id,
                lease_seconds=60,
            )

        # The transaction has successfully committed here.

    return claim


async def dispatch_once(db: Database, *, tenant_id: UUID, publisher: Publisher) -> bool:
    """Publish one committed reservation outside the DB transaction.

    True means an entry was attempted, not necessarily delivered. Cancellation or
    a bookkeeping failure leaves a lease that another dispatcher can reclaim.
    """
    claim = await reserve_next_dispatch(db, tenant_id=tenant_id)
    if claim is None:
        return False

    published = False
    try:
        # Shorter than the 60s reservation. Timeout means delivery is uncertain.
        async with asyncio.timeout(15):
            await publisher.publish(claim)
        published = True
    except Exception:
        # No exception strings: broker errors can contain credential-bearing URLs.
        logger.warning("outbox_publish_unconfirmed", extra={"outbox_id": str(claim.outbox_id)})

    # Retry indefinitely at a capped rate; a broker outage must not lose a job.
    delay = min(300, 5 * 2 ** min(claim.attempts - 1, 6) * random.uniform(0.8, 1.2))
    async with db.session() as session:
        async with session.begin():
            await session.execute(
                text("SELECT set_config('intelligence.tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            recorded = await finish_dispatch(
                session,
                claim=claim,
                published=published,
                retry_seconds=delay,
            )
    if not recorded:
        logger.warning("outbox_lease_lost", extra={"outbox_id": str(claim.outbox_id)})
    return True
