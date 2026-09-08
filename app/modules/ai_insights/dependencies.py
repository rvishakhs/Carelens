"""Public dependency-provider surface -- `handover` imports AIInsightReader from
ports.py and get_ai_insight_reader from here, never ai_insights.repository."""

from collections.abc import AsyncIterator

from fastapi import Depends

from app import AIInsightReader
from app import AIInsightRepository
from app import get_current_user
from app import CurrentUser
from app import rls_session


async def get_ai_insight_reader(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncIterator[AIInsightReader]:
    async with rls_session(current_user.care_home_id, current_user.id, current_user.floor_ids) as session:
        yield AIInsightRepository(session)
