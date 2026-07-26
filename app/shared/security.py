"""Low-level security primitives. Authentication itself is never hand-rolled -- it's
delegated to the OIDC provider (Keycloak). This module only holds primitives every
module might need: hashing non-auth secrets, generating opaque tokens, constant-time
comparisons."""

import hashlib
import hmac
import secrets


def generate_opaque_token(n_bytes: int = 32) -> str:
    """For idempotency keys, pseudonymisation salts, etc. -- not for password hashing."""
    return secrets.token_urlsafe(n_bytes)


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def hmac_pseudonym(value: str, secret_key: str) -> str:
    """Deterministic, keyed hash used by ai_gateway's pseudonymiser to derive stable
    per-resident tokens without storing the mapping in the hash itself."""
    digest = hmac.new(secret_key.encode("utf-8"), value.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()[:16]