"""Public dependency-provider surface -- other modules import ObservationReader from
ports.py and get_observation_reader from here, never observations.repository."""

from collections.abc import AsyncIterator

from fastapi import Depends

from app.modules.identity.dependencies import get_current_user
from app.modules.identity.schemas import CurrentUser
from app.modules.observations.ports import ObservationReader
from app.modules.observations.repository import ObservationRepository
from app.shared.database import rls_session


async def get_observation_reader(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncIterator[ObservationReader]:
    async with rls_session(current_user.care_home_id, current_user.id) as session:
        yield ObservationRepository(session)
