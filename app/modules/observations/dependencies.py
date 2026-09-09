"""Public dependency-provider surface -- other modules import ObservationReader from
ports.py and get_observation_reader from here, never observations.repository."""

from collections.abc import AsyncIterator

from fastapi import Depends

from app import CurrentUser, ObservationReader, ObservationRepository, get_current_user, rls_session


async def get_observation_reader(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncIterator[ObservationReader]:
    async with rls_session(current_user.care_home_id, current_user.id, current_user.floor_ids) as session:
        yield ObservationRepository(session)
