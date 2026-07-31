"""Nightly + shift-end job: generate a daily summary for every active resident in
every care home. Failures degrade gracefully per-resident -- the handover view falls
back to raw structured data rather than the whole run blocking on one bad record.

Care-home enumeration: Phase 1 has no `care_homes` registry table (it's not in the
Phase 1 table list), so this job takes `care_home_ids` explicitly. When multi-tenant
admin lands, replace this with a query against a system DB role that bypasses RLS only
to enumerate tenants (e.g. `CREATE ROLE carelens_scheduler BYPASSRLS`) -- never to read
tenant data itself.

Idempotency: summaries has no UNIQUE(resident_id, date) constraint yet, so rerunning
this job within the same day creates a duplicate AIOutput row rather than erroring.
Add that constraint in the Alembic migration before relying on at-most-once semantics.
"""

import uuid

from app.container import Container
from app.modules.ai_gateway.pseudonymiser import Pseudonymiser
from app.modules.ai_gateway.repository import PseudonymMappingRepository
from app.modules.ai_gateway.service import AIGatewayService
from app.modules.floors.repository import FloorRepository
from app.modules.observations.repository import ObservationRepository
from app.modules.residents.repository import ResidentRepository
from app.modules.summaries.repository import SummaryRepository
from app.modules.summaries.service import SummaryService
from app.shared.database import rls_session
from app.shared.telemetry import get_logger

logger = get_logger(__name__)

# Placeholder actor for the RLS `app.user_id` GUC -- this job has no human actor.
_SYSTEM_ACTOR = uuid.UUID(int=0)


async def run_summary_job(container: Container, care_home_ids: list[uuid.UUID]) -> None:
    for care_home_id in care_home_ids:
        # A scheduled job has no user_floor_links of its own -- it operates across
        # every floor in the home, the same way an admin/headoffice session would.
        async with rls_session(care_home_id, _SYSTEM_ACTOR) as session:
            floor_ids = [f.id for f in await FloorRepository(session).list_active()]

        async with rls_session(care_home_id, _SYSTEM_ACTOR, floor_ids) as session:
            residents = await ResidentRepository(session).list_active_residents()

        for resident in residents:
            try:
                async with rls_session(care_home_id, _SYSTEM_ACTOR, floor_ids) as session:
                    mapping_repository = PseudonymMappingRepository(session, container.settings.secret_key)
                    ai_gateway = AIGatewayService(container.llm_provider, Pseudonymiser(mapping_repository))
                    service = SummaryService(
                        repository=SummaryRepository(session),
                        observation_reader=ObservationRepository(session),
                        resident_reader=ResidentRepository(session),
                        ai_gateway=ai_gateway,
                        event_bus=container.event_bus,
                    )
                    await service.generate_daily_summary(care_home_id, resident.id)
            except Exception:
                logger.exception(
                    "summary_job_failed_for_resident",
                    care_home_id=str(care_home_id),
                    resident_id=str(resident.id),
                )
