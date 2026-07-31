"""Public dependency-provider surface -- other modules import CareEventReader from
ports.py and get_care_event_reader from here, never care_recording.repository."""

from collections.abc import AsyncIterator

from fastapi import Depends

from app.modules.care_recording.ports import CareEventReader
from app.modules.care_recording.repository import CareRecordingRepository
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.schemas import CurrentUser
from app.shared.database import rls_session


async def get_care_event_reader(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncIterator[CareEventReader]:
    async with rls_session(current_user.care_home_id, current_user.id, current_user.floor_ids) as session:
        yield CareRecordingRepository(session)
