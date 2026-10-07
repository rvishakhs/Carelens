"""Worker authentication and fresh CareLens authority; no application imports."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, TypeAdapter, ValidationError

from intelligence.core.errors import ExecutionAuthorisationDenied, ExecutionAuthorisationUnavailable
from intelligence.handover.authorization import ServiceGrant, StaffGrant


def require_secure_endpoint(url: str) -> None:
    """Credentials may use HTTP only on explicit loopback development URLs."""
    parsed = urlparse(url)
    local_http = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or (parsed.scheme != "https" and not local_http)
    ):
        raise ValueError("Service endpoints require HTTPS, except loopback development URLs")


@dataclass(frozen=True)
class WorkerCredentials:
    service_identity: str
    access_token: SecretStr
    expires_at: datetime


class TokenResponse(BaseModel):
    access_token: SecretStr = Field(min_length=1)
    token_type: str
    expires_in: int = Field(gt=0)


class KeycloakCredentialProvider:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        token_url: str,
        client_id: str,
        client_secret: SecretStr,
        expected_service_identity: str,
        minimum_lifetime_seconds: int = 120,
    ) -> None:
        self._client = client
        require_secure_endpoint(token_url)
        self._token_url = token_url
        self._client_id = client_id
        self._secret = client_secret
        self._identity = expected_service_identity
        self._minimum_lifetime = minimum_lifetime_seconds

    async def obtain(self) -> WorkerCredentials:
        requested_at = datetime.now(UTC)
        try:
            response = await self._client.post(
                self._token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._secret.get_secret_value(),
                },
                follow_redirects=False,
            )
        except httpx.RequestError:
            raise ExecutionAuthorisationUnavailable("Worker authentication unavailable") from None
        if response.status_code in {400, 401, 403}:
            raise ExecutionAuthorisationDenied("Worker credentials rejected")
        if response.status_code != 200:
            raise ExecutionAuthorisationUnavailable("Worker authentication failed")
        try:
            token = TokenResponse.model_validate_json(response.content, strict=True)
        except ValidationError:
            raise ExecutionAuthorisationUnavailable("Invalid token response") from None
        expires_at = requested_at + timedelta(seconds=token.expires_in)
        if (
            token.token_type.lower() != "bearer"
            or (expires_at - datetime.now(UTC)).total_seconds() < self._minimum_lifetime
        ):
            raise ExecutionAuthorisationUnavailable("Unsupported or short-lived service token")
        return WorkerCredentials(self._identity, token.access_token, expires_at)


class EligibilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: UUID
    resident_id: UUID
    eligible: bool


class HttpCareLensAuthorityReader:
    def __init__(self, *, client: httpx.AsyncClient, access_token: SecretStr) -> None:
        self._client = client
        self._token = access_token

    async def _get(self, path: str, *, tenant_id: UUID) -> bytes:
        try:
            response = await self._client.get(
                path,
                params={"tenant_id": str(tenant_id)},
                headers={"Authorization": f"Bearer {self._token.get_secret_value()}"},
                follow_redirects=False,
            )
        except httpx.RequestError:
            raise ExecutionAuthorisationUnavailable("CareLens authority unavailable") from None
        if response.status_code in {401, 403}:
            raise ExecutionAuthorisationDenied("CareLens refused authority access")
        if response.status_code != 200:
            raise ExecutionAuthorisationUnavailable("CareLens authority check failed")
        return response.content

    async def service_grant(self, *, tenant_id: UUID) -> ServiceGrant:
        body = await self._get("/internal/intelligence/authority/service", tenant_id=tenant_id)
        try:
            return TypeAdapter(ServiceGrant).validate_json(body, strict=True)
        except ValidationError:
            raise ExecutionAuthorisationUnavailable("Invalid service authority response") from None

    async def staff_grant(self, *, tenant_id: UUID, actor_id: UUID) -> StaffGrant:
        body = await self._get(f"/internal/intelligence/authority/staff/{actor_id}", tenant_id=tenant_id)
        try:
            return TypeAdapter(StaffGrant).validate_json(body, strict=True)
        except ValidationError:
            raise ExecutionAuthorisationUnavailable("Invalid staff authority response") from None

    async def resident_eligible(self, *, tenant_id: UUID, resident_id: UUID) -> bool:
        body = await self._get(
            f"/internal/intelligence/authority/residents/{resident_id}/eligibility",
            tenant_id=tenant_id,
        )
        try:
            result = EligibilityResponse.model_validate_json(body, strict=True)
        except ValidationError:
            raise ExecutionAuthorisationUnavailable("Invalid eligibility response") from None
        if result.tenant_id != tenant_id or result.resident_id != resident_id:
            raise ExecutionAuthorisationUnavailable("Eligibility scope mismatch")
        return result.eligible
