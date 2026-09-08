"""Dependency injection wiring: concrete adapters -> abstract ports.

Swapping an adapter (Bedrock instead of FakeLLM, Redis pub/sub instead of the
in-memory bus) is a change to this file plus config.py -- never to the modules
that consume the port.
"""

from dataclasses import dataclass

from app import Settings
from app import LLMProvider
from app import AttentionRanker
from app import PermissionRegistry
from app import IdentityProviderAdmin, TokenVerifier
from app import NoteStructurer
from app import EventBus, InMemoryEventBus


@dataclass
class Container:
    """Grab-bag of shared ports handed to every module's register(). Modules also
    receive an RLS-scoped DB session per-request via FastAPI dependencies, not via
    the container -- the container only holds process-lifetime singletons. Services
    are constructed per-request from these ports (see each module's router.py), not
    stored here, so the container stays adapters-only.

    permission_registry is the one exception that isn't a port/adapter pair -- it's a
    process-lifetime cache in front of the role_permissions table (see
    permission_registry.py's docstring), not a swappable implementation."""

    settings: Settings
    event_bus: EventBus
    llm_provider: LLMProvider
    token_verifier: TokenVerifier
    identity_provider_admin: IdentityProviderAdmin
    note_structurer: NoteStructurer
    attention_ranker: AttentionRanker
    permission_registry: PermissionRegistry


def build_container(settings: Settings) -> Container:
    return Container(
        settings=settings,
        event_bus=InMemoryEventBus(),
        llm_provider=_build_llm_provider(settings),
        token_verifier=_build_token_verifier(settings),
        identity_provider_admin=_build_identity_provider_admin(settings),
        note_structurer=_build_note_structurer(settings),
        attention_ranker=_build_attention_ranker(),
        permission_registry=PermissionRegistry(),
    )


def _build_attention_ranker() -> AttentionRanker:
    from app import RecencyAttentionRanker

    return RecencyAttentionRanker()


def _build_note_structurer(settings: Settings) -> NoteStructurer:
    from app import RuleBasedNoteStructurer

    return RuleBasedNoteStructurer()


def _build_token_verifier(settings: Settings) -> TokenVerifier:
    from app import KeycloakTokenVerifier

    return KeycloakTokenVerifier(issuer=settings.oidc_issuer, audience=settings.oidc_audience)


def _build_identity_provider_admin(settings: Settings) -> IdentityProviderAdmin:
    from app import KeycloakAdminClient

    return KeycloakAdminClient(
        server_url=settings.KEYCLOAK_SERVER,
        realm_name=settings.KEYCLOAK_REALM,
        client_id=settings.KEYCLOAK_CLIENT_ID,
        client_secret=settings.keycloak_admin_client_secret,
    )


def _build_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "fake":
        from app import FakeLLMProvider

        return FakeLLMProvider()

    if settings.llm_provider == "local":
        from app import LocalLLMProvider

        return LocalLLMProvider(model=settings.llm_model)

    from app import RealLLMProvider

    return RealLLMProvider(api_key=settings.llm_api_key, model=settings.llm_model)