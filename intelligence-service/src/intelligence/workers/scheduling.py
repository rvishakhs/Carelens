"""Reconcile completed shifts into durable jobs; never call the model here."""

import asyncio
import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy import text

from intelligence.config import (
    CareLensSettings,
    DispatcherSettings,
    ScheduleSettings,
    Settings,
    WorkerIdentitySettings,
)
from intelligence.connectors.authority import (
    HttpCareLensAuthorityReader,
    KeycloakCredentialProvider,
    require_secure_endpoint,
)
from intelligence.core.contracts import ExecutionContext
from intelligence.handover.contracts import HandoverSubmissionRequest
from intelligence.handover.shifts import completed_shifts
from intelligence.handover.validation import validate_completed_shift
from intelligence.persistence.database import Database
from intelligence.persistence.repositories import create_handover_job, find_existing_handover


async def submit_scheduled(
    db, *, context: ExecutionContext, request: HandoverSubmissionRequest, timezone: str
):
    if (
        context.trigger != "scheduled"
        or not {"handover:generate", "handover:schedule"} <= context.permissions
    ):
        raise ValueError("Scheduling authority required")
    if request.resident_id not in context.authorised_resident_ids:
        raise ValueError("Resident outside scheduling scope")
    validate_completed_shift(request, care_home_timezone=timezone, now=datetime.now(UTC))
    async with db.session() as session:
        async with session.begin():
            await session.execute(
                text("SELECT set_config('intelligence.tenant_id', :tenant, true)"),
                {"tenant": str(context.tenant_id)},
            )
            # Shared with manual submission: a repeated sweep or racing click reuses the same job.
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": f"handover:{context.tenant_id}:{request.resident_id}"},
            )
            job = await find_existing_handover(
                session,
                tenant_id=context.tenant_id,
                resident_id=request.resident_id,
                shift_start=request.shift_start,
                shift_end=request.shift_end,
            )
            if job is None:
                job = await create_handover_job(
                    session, context=context, request=request, care_home_timezone=timezone
                )
            return job.id


async def run_schedule_sweep():
    schedule = ScheduleSettings()
    if not schedule.enabled:
        return
    settings, identity, carelens = Settings(), WorkerIdentitySettings(), CareLensSettings()
    require_secure_endpoint(carelens.base_url)
    shifts = completed_shifts(
        now=datetime.now(UTC), timezone=settings.care_home_timezone, count=schedule.catch_up_shifts
    )
    db = Database(settings.database_url.get_secret_value())
    logger = logging.getLogger(__name__)
    try:
        async with (
            httpx.AsyncClient(timeout=10, follow_redirects=False) as token_client,
            httpx.AsyncClient(
                base_url=carelens.base_url,
                timeout=carelens.timeout_seconds,
                follow_redirects=False,
            ) as client,
        ):
            credential_provider = KeycloakCredentialProvider(
                client=token_client,
                token_url=identity.token_url,
                client_id=identity.client_id,
                client_secret=identity.client_secret,
                expected_service_identity=identity.service_identity,
                minimum_lifetime_seconds=identity.minimum_token_lifetime_seconds,
            )
            for tenant_id in dict.fromkeys(DispatcherSettings().tenant_ids):
                try:
                    credentials = await credential_provider.obtain()
                    reader = HttpCareLensAuthorityReader(client=client, access_token=credentials.access_token)
                    grant = await reader.service_grant(tenant_id=tenant_id)
                    if (
                        grant.tenant_id != tenant_id
                        or grant.service_identity != identity.service_identity
                        or not {"handover:generate", "handover:schedule"} <= grant.permissions
                    ):
                        logger.warning("handover_schedule_authority_denied")
                        continue
                    for resident_id in sorted(grant.resident_ids, key=str):
                        try:
                            if (credentials.expires_at - datetime.now(UTC)).total_seconds() < 60:
                                credentials = await credential_provider.obtain()
                                reader = HttpCareLensAuthorityReader(
                                    client=client, access_token=credentials.access_token
                                )
                            if not await reader.resident_eligible(
                                tenant_id=tenant_id, resident_id=resident_id
                            ):
                                continue
                            context = ExecutionContext(
                                tenant_id=tenant_id,
                                service_identity=grant.service_identity,
                                trigger="scheduled",
                                authorised_resident_ids=frozenset({resident_id}),
                                permissions=grant.permissions,
                            )
                            for shift in shifts:
                                async with asyncio.timeout(30):
                                    await submit_scheduled(
                                        db,
                                        context=context,
                                        timezone=settings.care_home_timezone,
                                        request=HandoverSubmissionRequest(
                                            resident_id=resident_id,
                                            shift_start=shift.start,
                                            shift_end=shift.end,
                                        ),
                                    )
                        except Exception:
                            logger.error("handover_schedule_resident_unavailable")
                except Exception:
                    logger.error("handover_schedule_tenant_unavailable")
    finally:
        await db.close()
