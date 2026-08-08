"""Audit subscribes to every domain event that matters for care-record accountability.
Adding a new hazard-relevant event elsewhere in the codebase means adding one line
here -- never editing the module that publishes it.

`audit_action` (migrations/versions/0001) is a coarse, fixed enum -- view / create /
update / approve / export / emergency_access / login / login_failed -- deliberately
coarser than the domain events feeding it. The "what specifically happened" detail
(e.g. that an observation was flagged implausible) lives on the entity's own row, not
spelled out in the audit action; `entity_type` + `entity_id` is enough to join back to
it.
"""

import uuid

from fastapi import FastAPI

from app.container import Container
from app.modules.ai_insights.events import AIAlertAcknowledged, AIAlertRaised
from app.modules.audit.models import AuditAction
from app.modules.audit.repository import AuditRepository
from app.modules.audit.router import router
from app.modules.audit.service import AuditService
from app.modules.care_recording.events import CareEventRecorded
from app.modules.floors.events import FloorCreated, UserFloorAccessGranted, UserFloorAccessRevoked
from app.modules.handover.events import RecordViewed
from app.modules.identity.events import (
    MfaChallengeFailed,
    StaffMemberCreated,
    StaffMemberUpdated,
    StaffPasswordReset,
    UserLoggedIn,
)
from app.modules.observations.events import ObservationRecorded
from app.modules.residents.events import ResidentCreated
from app.modules.summaries.events import SummaryGenerated, SummaryReviewed
from app.shared.database import rls_session
from app.shared.events import DomainEvent

# Placeholder actor for the RLS `app.user_id` GUC when an event carries no actor
# (e.g. a scheduled job). Not a real user row -- RLS only keys off care_home_id.
_SYSTEM_ACTOR = uuid.UUID(int=0)


async def _log(event: DomainEvent, *, action: AuditAction, entity_type: str, entity_id: uuid.UUID | None) -> None:
    async with rls_session(event.care_home_id, event.actor_user_id or _SYSTEM_ACTOR) as session:
        await AuditService(AuditRepository(session)).log(
            care_home_id=event.care_home_id,
            actor_id=event.actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
        )


async def _on_user_logged_in(event: UserLoggedIn) -> None:
    await _log(event, action=AuditAction.LOGIN, entity_type="user", entity_id=event.user_id)


async def _on_mfa_challenge_failed(event: MfaChallengeFailed) -> None:
    await _log(event, action=AuditAction.LOGIN_FAILED, entity_type="user", entity_id=event.user_id)


async def _on_staff_member_created(event: StaffMemberCreated) -> None:
    await _log(event, action=AuditAction.CREATE, entity_type="user", entity_id=event.user_id)


async def _on_staff_member_updated(event: StaffMemberUpdated) -> None:
    await _log(event, action=AuditAction.UPDATE, entity_type="user", entity_id=event.user_id)


async def _on_staff_password_reset(event: StaffPasswordReset) -> None:
    await _log(event, action=AuditAction.UPDATE, entity_type="user", entity_id=event.user_id)


async def _on_resident_created(event: ResidentCreated) -> None:
    await _log(event, action=AuditAction.CREATE, entity_type="resident", entity_id=event.resident_id)


async def _on_observation_recorded(event: ObservationRecorded) -> None:
    await _log(event, action=AuditAction.CREATE, entity_type="observation", entity_id=event.observation_id)


async def _on_summary_generated(event: SummaryGenerated) -> None:
    await _log(event, action=AuditAction.CREATE, entity_type="ai_output", entity_id=event.summary_id)


async def _on_summary_reviewed(event: SummaryReviewed) -> None:
    await _log(event, action=AuditAction.UPDATE, entity_type="ai_output", entity_id=event.summary_id)


async def _on_record_viewed(event: RecordViewed) -> None:
    await _log(event, action=AuditAction.VIEW, entity_type="resident", entity_id=event.resident_id)


async def _on_floor_created(event: FloorCreated) -> None:
    await _log(event, action=AuditAction.CREATE, entity_type="floor", entity_id=event.floor_id)


async def _on_user_floor_access_granted(event: UserFloorAccessGranted) -> None:
    await _log(event, action=AuditAction.APPROVE, entity_type="user_floor_link", entity_id=event.user_id)


async def _on_user_floor_access_revoked(event: UserFloorAccessRevoked) -> None:
    await _log(event, action=AuditAction.UPDATE, entity_type="user_floor_link", entity_id=event.user_id)


async def _on_care_event_recorded(event: CareEventRecorded) -> None:
    await _log(event, action=AuditAction.CREATE, entity_type="care_event", entity_id=event.care_event_id)


async def _on_ai_alert_raised(event: AIAlertRaised) -> None:
    await _log(event, action=AuditAction.CREATE, entity_type="ai_alert", entity_id=event.alert_id)


async def _on_ai_alert_acknowledged(event: AIAlertAcknowledged) -> None:
    await _log(event, action=AuditAction.APPROVE, entity_type="ai_alert", entity_id=event.alert_id)


def register(app: FastAPI, container: Container) -> None:
    app.include_router(router)

    container.event_bus.subscribe(UserLoggedIn, _on_user_logged_in)
    container.event_bus.subscribe(MfaChallengeFailed, _on_mfa_challenge_failed)
    container.event_bus.subscribe(StaffMemberCreated, _on_staff_member_created)
    container.event_bus.subscribe(StaffMemberUpdated, _on_staff_member_updated)
    container.event_bus.subscribe(StaffPasswordReset, _on_staff_password_reset)
    container.event_bus.subscribe(ResidentCreated, _on_resident_created)
    container.event_bus.subscribe(ObservationRecorded, _on_observation_recorded)
    container.event_bus.subscribe(SummaryGenerated, _on_summary_generated)
    container.event_bus.subscribe(SummaryReviewed, _on_summary_reviewed)
    container.event_bus.subscribe(RecordViewed, _on_record_viewed)
    container.event_bus.subscribe(FloorCreated, _on_floor_created)
    container.event_bus.subscribe(UserFloorAccessGranted, _on_user_floor_access_granted)
    container.event_bus.subscribe(UserFloorAccessRevoked, _on_user_floor_access_revoked)
    container.event_bus.subscribe(CareEventRecorded, _on_care_event_recorded)
    container.event_bus.subscribe(AIAlertRaised, _on_ai_alert_raised)
    container.event_bus.subscribe(AIAlertAcknowledged, _on_ai_alert_acknowledged)
