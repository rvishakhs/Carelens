"""Public dependency-provider surface for cross-module reads. Other modules import
`ResidentReader` from ports.py and `get_resident_reader`/`get_scoped_resident_reader`
from here -- never residents.repository or residents.models directly."""

import uuid
from collections.abc import AsyncIterator

from fastapi import Depends

from app.modules.identity.dependencies import get_current_user, get_floor_scope
from app.modules.identity.schemas import CurrentUser
from app.modules.residents.ports import ResidentReader
from app.modules.residents.repository import ResidentRepository
from app.shared.database import rls_session


async def get_resident_reader(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncIterator[ResidentReader]:
    async with rls_session(current_user.care_home_id, current_user.id, current_user.floor_ids) as session:
        yield ResidentRepository(session)


async def get_scoped_resident_reader(
    current_user: CurrentUser = Depends(get_current_user),
    floor_ids: list[uuid.UUID] = Depends(get_floor_scope),
) -> AsyncIterator[ResidentReader]:
    """Same as get_resident_reader, but honours the caller's optional ?floor_id=
    (get_floor_scope) instead of always using every authorised floor -- for
    resident-browsing views (e.g. handover) where "just my floor" vs. "everything
    I'm authorised for" should be the viewer's per-request choice."""
    async with rls_session(current_user.care_home_id, current_user.id, floor_ids) as session:
        yield ResidentRepository(session)
