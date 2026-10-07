from datetime import datetime
from typing import Literal
from uuid import UUID

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, JsonValue, SecretStr, TypeAdapter


class CareLensUnavailable(Exception):
    pass


class CareLensAccessDenied(Exception):
    pass


class CareLensResourceUnavailable(Exception):
    pass


class CareLensPaginationIncomplete(CareLensUnavailable):
    """Traversal could not finish safely; callers must not use partial records."""


class ResidentResponse(BaseModel):
    # Validate only what this first operation needs.
    # Add fields deliberately as the integration develops.
    model_config = ConfigDict(extra="ignore")

    id: UUID


class ObservationResponse(BaseModel):
    """Transport record only: contains sensitive source data, not gateway-safe evidence."""

    model_config = ConfigDict(extra="ignore")

    id: UUID
    resident_id: UUID
    type: str
    value: dict[str, JsonValue]
    recorded_at: AwareDatetime
    recorded_by: UUID | None
    is_implausible: bool
    source_type: str
    time_precision: Literal["timestamp", "date"]
    source_date: str | None = None


_observations = TypeAdapter(list[ObservationResponse])


class CareLensClient:
    def __init__(self, client: httpx.AsyncClient, *, service_tenant_id: UUID | None = None) -> None:
        self._client = client
        self._service_tenant_id = service_tenant_id

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
                    "Authorization": (f"Bearer {access_token.get_secret_value()}"),
                },
            )
        except httpx.RequestError:
            raise CareLensUnavailable("CareLens could not be reached") from None

        if response.status_code in {401, 403}:
            raise CareLensAccessDenied("CareLens rejected access")

        if response.status_code == 404:
            raise CareLensResourceUnavailable("Resident unavailable")

        if response.status_code != 200:
            raise CareLensUnavailable("CareLens returned an unexpected response")

        try:
            resident = ResidentResponse.model_validate(response.json())
        except ValueError:
            raise CareLensUnavailable("CareLens returned an invalid resident response") from None

        if resident.id != resident_id:
            raise CareLensUnavailable("CareLens returned an unexpected resident")

        return resident

    async def list_observations_page(
        self,
        resident_id: UUID,
        access_token: SecretStr,
        *,
        since: datetime,
        until: datetime,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ObservationResponse]:
        """Read one raw page; neither an empty page nor a full page proves complete history.

        The API can include native observations as well as the 14 clinical sources.
        Source allowlisting belongs in normalization, after raw pagination accounting.
        recorded_at follows the API's projection semantics, not necessarily entry time.
        """
        if since.utcoffset() is None or until.utcoffset() is None:
            raise ValueError("since and until must include a timezone")
        if since >= until:
            raise ValueError("since must precede until")
        if not 1 <= limit <= 500 or offset < 0:
            raise ValueError("limit must be 1–500 and offset must be non-negative")

        try:
            response = await self._client.get(
                "/internal/intelligence/observations" if self._service_tenant_id is not None else "/observations",
                params={
                    **({"tenant_id": str(self._service_tenant_id)} if self._service_tenant_id else {}),
                    "resident_id": str(resident_id),
                    "since": since.isoformat(),
                    "until": until.isoformat(),
                    "limit": limit,
                    "offset": offset,
                },
                follow_redirects=False,
                headers={"Authorization": f"Bearer {access_token.get_secret_value()}"},
            )
        except httpx.RequestError:
            raise CareLensUnavailable("CareLens could not be reached") from None

        if response.status_code in {401, 403}:
            raise CareLensAccessDenied("CareLens rejected access")
        if response.status_code == 404:
            raise CareLensResourceUnavailable("Observations unavailable")
        if response.status_code != 200:
            raise CareLensUnavailable("CareLens returned an unexpected response")

        try:
            records = _observations.validate_python(response.json())
        except ValueError:
            raise CareLensUnavailable("CareLens returned an invalid observations response") from None

        if len(records) > limit:
            raise CareLensUnavailable("CareLens exceeded the requested page size")
        if any(record.resident_id != resident_id for record in records):
            raise CareLensUnavailable("CareLens returned an unexpected resident")
        if any(not since <= record.recorded_at < until for record in records):
            raise CareLensUnavailable("CareLens returned observations outside the requested period")
        return records

    async def list_observations(
        self,
        resident_id: UUID,
        access_token: SecretStr,
        *,
        since: datetime,
        until: datetime,
        page_size: int = 100,
        max_pages: int = 100,
    ) -> list[ObservationResponse]:
        """Traverse raw pages until an empty page, without claiming snapshot consistency.

        max_pages includes the terminating empty-page request. Short non-empty pages
        still advance by their raw row count. No source filtering occurs here.
        Duplicate composite identities indicate an unstable traversal and fail closed;
        undetected omissions remain possible with the backend's offset pagination.
        """
        if type(max_pages) is not int or not 1 <= max_pages <= 1000:
            raise ValueError("max_pages must be an integer between 1 and 1000")
        if type(page_size) is not int or not 1 <= page_size <= 500:
            raise ValueError("page_size must be an integer between 1 and 500")

        records: list[ObservationResponse] = []
        seen: set[tuple[str, UUID]] = set()
        offset = 0
        for _ in range(max_pages):
            page = await self.list_observations_page(
                resident_id, access_token, since=since, until=until, limit=page_size, offset=offset
            )
            if not page:
                return records
            for record in page:
                identity = (record.source_type, record.id)
                if identity in seen:
                    raise CareLensPaginationIncomplete("CareLens returned duplicate observation identities")
                seen.add(identity)
            records.extend(page)
            offset += len(page)

        raise CareLensPaginationIncomplete("CareLens observation pagination reached its page limit")
