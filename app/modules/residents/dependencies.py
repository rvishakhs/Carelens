"""Public dependency-provider surface for cross-module reads. Other modules import
`ResidentReader` from ports.py and `get_resident_reader` from here -- never
residents.repository or residents.models directly."""

from collections.abc import AsyncIterator

from fastapi import Depends

from app.modules.identity.dependencies import get_current_user
from app.modules.identity.schemas import CurrentUser
from app.modules.residents.ports import ResidentReader
from app.modules.residents.repository import ResidentRepository
from app.shared.database import rls_session


async def get_resident_reader(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncIterator[ResidentReader]:
    async with rls_session(current_user.care_home_id, current_user.id) as session:
        yield ResidentRepository(session)
