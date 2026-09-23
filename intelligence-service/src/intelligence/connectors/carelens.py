from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, SecretStr


class CareLensUnavailable(Exception):
    pass


class CareLensAccessDenied(Exception):
    pass


class CareLensResourceUnavailable(Exception):
    pass


class ResidentResponse(BaseModel):
    # Validate only what this first operation needs.
    # Add fields deliberately as the integration develops.
    model_config = ConfigDict(extra="ignore")

    id: UUID



class CareLensClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def get_resident(
        self,
        resident_id: UUID,
        access_token: SecretStr,
    ) -> ResidentResponse:
        try:
            response = await self._client.get(
                f"/residents/{resident_id}",
                follow_redirects=False,
                headers={
                    "Authorization": (
                        f"Bearer {access_token.get_secret_value()}"
                    ),
                },
            )
        except httpx.RequestError:
            raise CareLensUnavailable(
                "CareLens could not be reached"
            ) from None

        if response.status_code in {401, 403}:
            raise CareLensAccessDenied(
                "CareLens rejected access"
            )

        if response.status_code == 404:
            raise CareLensResourceUnavailable(
                "Resident unavailable"
            )

        if response.status_code != 200:
            raise CareLensUnavailable(
                "CareLens returned an unexpected response"
            )

        try:
            resident = ResidentResponse.model_validate(
                response.json()
            )
        except ValueError:
            raise CareLensUnavailable(
                "CareLens returned an invalid resident response"
            ) from None

        if resident.id != resident_id:
            raise CareLensUnavailable(
                "CareLens returned an unexpected resident"
            )

        return resident
