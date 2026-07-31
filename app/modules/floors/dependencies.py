"""Public dependency-provider surface -- other modules import FloorReader from
ports.py and get_floor_reader_for from here, never floors.repository or floors.models.

Deliberately does NOT depend on identity.dependencies.get_current_user: identity
itself needs a FloorReader (to resolve a user's authorised floors right after token
verification, before CurrentUser even exists), so that would be circular. This takes
care_home_id/user_id directly instead -- a plain async context manager (not a FastAPI
generator dependency), since identity calls it directly rather than through Depends().
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.modules.floors.ports import FloorReader
from app.modules.floors.repository import FloorRepository
from app.shared.database import rls_session


@asynccontextmanager
async def get_floor_reader_for(care_home_id: uuid.UUID, user_id: uuid.UUID) -> AsyncIterator[FloorReader]:
    async with rls_session(care_home_id, user_id) as session:
        yield FloorRepository(session)
