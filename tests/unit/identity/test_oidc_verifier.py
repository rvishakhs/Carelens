"""Exercise real JWT validation without a database or a running Keycloak."""

import time
from unittest.mock import AsyncMock

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from app import UnauthenticatedError
from app.modules.identity.adapters.oidc_verifier import KeycloakTokenVerifier

ISSUER = "https://identity.test/realms/CareLens"


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def verifier(signing_key):
    instance = KeycloakTokenVerifier(ISSUER, "carelens-api")
    instance._get_jwks = AsyncMock(return_value=signing_key.public_key())
    return instance


def claims():
    return {
        "iss": ISSUER,
        "aud": "carelens-api",
        "sub": "test-staff-subject",
        "exp": int(time.time()) + 300,
        "role": "nurse",
    }


@pytest.mark.parametrize("audience", ["carelens-api", ["account", "carelens-api"]])
async def test_accepts_intended_audience(verifier, signing_key, audience):
    payload = claims() | {"aud": audience}
    result = await verifier.verify(jwt.encode(payload, signing_key, algorithm="RS256"))
    assert result.subject == "test-staff-subject"
    assert result.role == "nurse"


@pytest.mark.parametrize("changes", [
    {"aud": "another-api"},
    {"iss": "https://other.test/realms/CareLens"},
    {"exp": int(time.time()) - 300},
    {"nbf": int(time.time()) + 300},
])
async def test_rejects_invalid_claims(verifier, signing_key, changes):
    token = jwt.encode(claims() | changes, signing_key, algorithm="RS256")
    with pytest.raises(UnauthenticatedError, match="Invalid or expired access token"):
        await verifier.verify(token)


@pytest.mark.parametrize("missing", ["aud", "iss", "exp", "sub"])
async def test_requires_claims(verifier, signing_key, missing):
    payload = claims()
    del payload[missing]
    with pytest.raises(UnauthenticatedError):
        await verifier.verify(jwt.encode(payload, signing_key, algorithm="RS256"))


async def test_rejects_untrusted_signature(verifier):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(UnauthenticatedError):
        await verifier.verify(jwt.encode(claims(), other_key, algorithm="RS256"))


async def test_rejects_disallowed_algorithm(verifier):
    token = jwt.encode(claims(), "test-only-hmac-key", algorithm="HS256")
    with pytest.raises(UnauthenticatedError):
        await verifier.verify(token)
