import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models import Role, User
from app.modules.identity.ports import TokenClaims
from app.shared.exceptions import UnauthenticatedError


class UserRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_oidc_subject(self, oidc_subject: str) -> User | None:
        result = await self._session.execute(select(User).where(User.oidc_subject == oidc_subject))
        return result.scalar_one_or_none()

    async def find_care_home_id_by_oidc_subject(self, oidc_subject: str) -> uuid.UUID | None:
        """Run this against `bootstrap_session()`, never a normal `rls_session()` --
        see that function's docstring. Only ever selects the one column needed to
        open the real tenant-scoped session; never used to read anything else."""
        result = await self._session.execute(
            select(User.care_home_id).where(User.oidc_subject == oidc_subject, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def sync_from_claims(self, claims: TokenClaims) -> User:
        """Re-syncs identity fields (email/display_name/role) from a verified token
        onto the local mirror row so Keycloak stays their source of truth. Never
        creates a user: a local row must already exist -- via a manager's "add staff"
        flow (identity/service.py's create_staff_member), which provisions the
        Keycloak account and this row together -- because care_home_id isn't on the
        token to guess from anymore."""
        user = await self.get_by_oidc_subject(claims.subject)
        if user is None:
            raise UnauthenticatedError(
                "no CareLens account found for this identity; ask a manager to add you as staff"
            )
        user.email = claims.email
        user.display_name = claims.display_name
        user.role = Role(claims.role)
        await self._session.flush()
        return user

    async def create_provisioned(
        self, *, care_home_id: uuid.UUID, oidc_subject: str, email: str, display_name: str, role: Role
    ) -> User:
        """Creates the local mirror row for a staff member already provisioned in
        Keycloak (identity/service.py's create_staff_member) -- the counterpart to
        sync_from_claims, which only ever updates an existing row."""
        user = User(
            oidc_subject=oidc_subject,
            care_home_id=care_home_id,
            email=email,
            display_name=display_name,
            role=role,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def list_active(self) -> list[User]:
        result = await self._session.execute(select(User).where(User.is_active, User.deleted_at.is_(None)))
        return list(result.scalars().all())