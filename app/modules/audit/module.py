"""Audit subscribes to every domain event that matters for care-record accountability.
Adding a new hazard-relevant event elsewhere in the codebase means adding one line
here -- never editing the module that publishes it."""

import uuid

from fastapi import FastAPI

from app.container import Container
from app.modules.audit.repository import AuditRepository
from app.modules.audit.router import router
from app.modules.audit.service import AuditService
from app.modules.handover.events import RecordViewed
from app.modules.identity.events import MfaChallengeFailed, UserLoggedIn
from app.modules.observations.events import ObservationRecorded
from app.modules.residents.events import ResidentCreated
from app.modules.summaries.events import SummaryGenerated, SummaryReviewed
from app.shared.database import rls_session
from app.shared.events import DomainEvent

# Placeholder actor for the RLS `app.user_id` GUC when an event carries no actor
# (e.g. a scheduled job). Not a real user row -- RLS only keys off care_home_id.
_SYSTEM_ACTOR = uuid.UUID(int=0)


async def _log(event: DomainEvent, *, action: str, entity_type: str, entity_id: uuid.UUID | None) -> None:
    async with rls_session(event.care_home_id, event.actor_user_id or _SYSTEM_ACTOR) as session:
        await AuditService(AuditRepository(session)).log(
            care_home_id=event.care_home_id,
            actor_user_id=event.actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
        )


async def _on_user_logged_in(event: UserLoggedIn) -> None:
    await _log(event, action="user.logged_in", entity_type="user", entity_id=event.user_id)


async def _on_mfa_challenge_failed(event: MfaChallengeFailed) -> None:
    await _log(event, action="user.mfa_challenge_failed", entity_type="user", entity_id=event.user_id)


async def _on_resident_created(event: ResidentCreated) -> None:
    await _log(event, action="resident.created", entity_type="resident", entity_id=event.resident_id)


async def _on_observation_recorded(event: ObservationRecorded) -> None:
    action = "observation.recorded_implausible" if event.is_implausible else "observation.recorded"
    await _log(event, action=action, entity_type="observation", entity_id=event.observation_id)


async def _on_summary_generated(event: SummaryGenerated) -> None:
    await _log(event, action="summary.generated", entity_type="ai_output", entity_id=event.summary_id)


async def _on_summary_reviewed(event: SummaryReviewed) -> None:
    await _log(event, action="summary.reviewed", entity_type="ai_output", entity_id=event.summary_id)


async def _on_record_viewed(event: RecordViewed) -> None:
    await _log(event, action="handover.record_viewed", entity_type="resident", entity_id=event.resident_id)


def register(app: FastAPI, container: Container) -> None:
    app.include_router(router)

    container.event_bus.subscribe(UserLoggedIn, _on_user_logged_in)
    container.event_bus.subscribe(MfaChallengeFailed, _on_mfa_challenge_failed)
    container.event_bus.subscribe(ResidentCreated, _on_resident_created)
    container.event_bus.subscribe(ObservationRecorded, _on_observation_recorded)
    container.event_bus.subscribe(SummaryGenerated, _on_summary_generated)
    container.event_bus.subscribe(SummaryReviewed, _on_summary_reviewed)
    container.event_bus.subscribe(RecordViewed, _on_record_viewed)
