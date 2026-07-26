"""Dependency injection wiring: concrete adapters -> abstract ports.

Swapping an adapter (Bedrock instead of FakeLLM, Redis pub/sub instead of the
in-memory bus) is a change to this file plus config.py -- never to the modules
that consume the port.
"""

from dataclasses import dataclass

from app.config import Settings
from app.modules.ai_gateway.ports import LLMProvider
from app.modules.handover.ports import AttentionRanker
from app.modules.identity.ports import TokenVerifier
from app.modules.observations.ports import NoteStructurer
from app.shared.events import EventBus, InMemoryEventBus


@dataclass
class Container:
    """Grab-bag of shared ports handed to every module's register(). Modules also
    receive an RLS-scoped DB session per-request via FastAPI dependencies, not via
    the container -- the container only holds process-lifetime singletons. Services
    are constructed per-request from these ports (see each module's router.py), not
    stored here, so the container stays adapters-only."""

    settings: Settings
    event_bus: EventBus
    llm_provider: LLMProvider
    token_verifier: TokenVerifier
    note_structurer: NoteStructurer
    attention_ranker: AttentionRanker


def build_container(settings: Settings) -> Container:
    return Container(
        settings=settings,
        event_bus=InMemoryEventBus(),
        llm_provider=_build_llm_provider(settings),
        token_verifier=_build_token_verifier(settings),
        note_structurer=_build_note_structurer(settings),
        attention_ranker=_build_attention_ranker(),
    )


def _build_attention_ranker() -> AttentionRanker:
    from app.modules.handover.adapters.recency_ranker import RecencyAttentionRanker

    return RecencyAttentionRanker()


def _build_note_structurer(settings: Settings) -> NoteStructurer:
    from app.modules.observations.adapters.rule_based_structurer import RuleBasedNoteStructurer

    return RuleBasedNoteStructurer()


def _build_token_verifier(settings: Settings) -> TokenVerifier:
    from app.modules.identity.adapters.oidc_verifier import KeycloakTokenVerifier

    return KeycloakTokenVerifier(issuer=settings.oidc_issuer, audience=settings.oidc_audience)


def _build_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "fake":
        from app.modules.ai_gateway.adapters.fake_llm import FakeLLMProvider

        return FakeLLMProvider()

    if settings.llm_provider == "local":
        from app.modules.ai_gateway.adapters.local_llm import LocalLLMProvider

        return LocalLLMProvider(model=settings.llm_model)

    from app.modules.ai_gateway.adapters.real_llm import RealLLMProvider

    return RealLLMProvider(api_key=settings.llm_api_key, model=settings.llm_model)