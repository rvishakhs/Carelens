from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models import Role, User
from app.modules.identity.ports import TokenClaims


class UserRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_oidc_subject(self, oidc_subject: str) -> User | None:
        result = await self._session.execute(select(User).where(User.oidc_subject == oidc_subject))
        return result.scalar_one_or_none()

    async def get_or_create_from_claims(self, claims: TokenClaims) -> User:
        """Just-in-time provisioning: the first time a Keycloak-verified token from a
        given subject is seen, mirror it locally so RLS/audit have a stable user_id.
        Role and profile fields are re-synced from claims on every call so Keycloak
        stays the source of truth."""
        user = await self.get_by_oidc_subject(claims.subject)
        if user is None:
            user = User(
                oidc_subject=claims.subject,
                care_home_id=claims.care_home_id,
                email=claims.email,
                display_name=claims.display_name,
                role=Role(claims.role),
            )
            self._session.add(user)
            await self._session.flush()
            return user

        user.email = claims.email
        user.display_name = claims.display_name
        user.role = Role(claims.role)
        await self._session.flush()
        return user