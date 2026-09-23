from uuid import UUID

from sqlalchemy import text

from intelligence.persistence.database import Database
from intelligence.persistence.outbox_repository import (
    ClaimedDispatch,
    claim_pending_dispatch,
)


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
                text(
                    "SELECT set_config("
                    "'intelligence.tenant_id', :tenant_id, true)"
                ),
                {"tenant_id": str(tenant_id)},
            )

            claim = await claim_pending_dispatch(
                session,
                tenant_id=tenant_id,
                lease_seconds=60,
            )

        # The transaction has successfully committed here.

    return claim