import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_gateway.models import PseudonymMapping
from app.shared.security import hmac_pseudonym


class PseudonymMappingRepository:
    def __init__(self, session: AsyncSession, secret_key: str):
        self._session = session
        self._secret_key = secret_key

    async def get_or_create_token(self, care_home_id: uuid.UUID, resident_id: uuid.UUID) -> str:
        result = await self._session.execute(
            select(PseudonymMapping).where(PseudonymMapping.resident_id == resident_id)
        )
        mapping = result.scalar_one_or_none()
        if mapping is not None:
            return mapping.token

        token = f"RESIDENT_{hmac_pseudonym(str(resident_id), self._secret_key).upper()}"
        mapping = PseudonymMapping(care_home_id=care_home_id, resident_id=resident_id, token=token)
        self._session.add(mapping)
        await self._session.flush()
        return token
