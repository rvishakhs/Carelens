import httpx
from pydantic import ValidationError

from intelligence.connectors.authority import require_secure_endpoint
from intelligence.core.contracts import Scope


class StaffUnauthenticated(Exception):
    """The staff access token is missing, invalid or expired."""


class StaffAccessDenied(Exception):
    """The authenticated staff member cannot access intelligence."""


class StaffIdentityUnavailable(Exception):
    """CareLens could not provide a valid authentication response."""


class CareLensStaffIdentityReader:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        base_url: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._url = (
            f"{base_url.rstrip('/')}/identity/intelligence-scope"
        )
        require_secure_endpoint(self._url)

        self._client = client
        self._timeout_seconds = timeout_seconds

    async def resolve(self, access_token: str) -> Scope:
        try:
            response = await self._client.get(
                self._url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                timeout=self._timeout_seconds,
                follow_redirects=False,
            )
        except httpx.RequestError:
            raise StaffIdentityUnavailable() from None

        if response.status_code == 401:
            raise StaffUnauthenticated()

        if response.status_code == 403:
            raise StaffAccessDenied()

        if response.status_code != 200:
            raise StaffIdentityUnavailable()

        try:
            return Scope.model_validate(response.json())
        except (ValueError, ValidationError):
            raise StaffIdentityUnavailable() from None