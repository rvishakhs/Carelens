from uuid import UUID, uuid4

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from intelligence.core.errors import HandoverLeaseLost
from intelligence.handover.contracts import (
    GenerationMetadata,
    HandoverRetrieval,
    ValidatedHandoverContent,
)
from intelligence.persistence.database import Database
from intelligence.persistence.job_repository import (
    ClaimedJob,
    JobExecutionSnapshot,
)
from intelligence.persistence.models import (
    EvidenceManifest,
    HandoverDraftVersion,
    HandoverJob,
)


async def persist_original_draft(
    session: AsyncSession,
    *,
    claim: ClaimedJob,
    snapshot: JobExecutionSnapshot,
    retrieval: HandoverRetrieval,
    content: ValidatedHandoverContent,
    generation: GenerationMetadata,
) -> UUID:
    if not session.in_transaction():
        raise RuntimeError("An explicit transaction is required")

    if (
        claim.tenant_id != snapshot.tenant_id
        or claim.job_id != snapshot.job_id
    ):
        raise ValueError("Claim and snapshot do not match")

    # Lock before checking database time: waiting for the lock may take time.
    job = await session.scalar(
        select(HandoverJob)
        .where(
            HandoverJob.tenant_id == claim.tenant_id,
            HandoverJob.id == claim.job_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    database_now = await session.scalar(select(func.clock_timestamp()))

    if (
        job is None
        or job.state != "running"
        or job.lease_token != claim.lease_token
        or job.lease_expires_at is None
        or job.lease_expires_at <= database_now
    ):
        raise HandoverLeaseLost("Job lease is no longer valid")

    if (
        job.resident_id != snapshot.resident_id
        or job.shift_start != snapshot.shift_start
        or job.shift_end != snapshot.shift_end
    ):
        raise ValueError("Job no longer matches the execution snapshot")

    if content.coverage_complete != retrieval.coverage_complete:
        raise ValueError("Content and retrieval coverage disagree")

    evidence = retrieval.evidence

    # Preserve every input source, including records used only as context.
    sources = [
        {
            "reference": record.reference.model_dump(mode="json"),
            "time_group": time_group,
            "effective_at": (
                record.effective_at.isoformat()
                if record.effective_at is not None else None
            ),
            "recorded_at": (
                record.recorded_at.isoformat()
                if record.recorded_at is not None else None
            ),
            "source_date": (
                record.source_date.isoformat()
                if record.source_date is not None else None
            ),
            "time_basis": record.time_basis,
            "time_precision": record.time_precision,
        }
        for time_group, records in (
            ("shift", evidence.shift_records),
            ("date_context", evidence.date_context),
            ("unknown_time", evidence.unknown_time_records),
        )
        for record in records
    ]

    warnings = [
        {"message": message}
        for message in dict.fromkeys(
            (*retrieval.warnings, *evidence.warnings, *content.warnings)
        )
    ]

    manifest_id = uuid4()
    draft_id = uuid4()

    session.add(
        EvidenceManifest(
            id=manifest_id,
            tenant_id=snapshot.tenant_id,
            resident_id=snapshot.resident_id,
            job_id=snapshot.job_id,
            attempt_token=claim.lease_token,
            retrieved_at=retrieval.retrieved_at,
            evidence_cutoff=retrieval.evidence_cutoff,
            coverage_complete=retrieval.coverage_complete,
            source_checkpoint=None,
            sources=sources,
            warnings=warnings,
        )
    )

    # Insert the manifest before the draft referencing it.
    await session.flush()

    session.add(
        HandoverDraftVersion(
            id=draft_id,
            tenant_id=snapshot.tenant_id,
            resident_id=snapshot.resident_id,
            job_id=snapshot.job_id,
            manifest_id=manifest_id,
            version_number=1,
            version_kind="ai_original",
            previous_version_id=None,
            authored_by=None,
            sections=[
                section.model_dump(mode="json")
                for section in content.sections
            ],
            warnings=warnings,
            agent_version=generation.agent_version,
            prompt_version=generation.prompt_version,
            gateway_version=generation.gateway_version,
            provider=generation.provider,
            model_version=generation.model_version,
            generated_at=generation.generated_at,
        )
    )

    await session.flush()

    # Recheck ownership and expiry at the final state transition.
    completed_job_id = await session.scalar(
        update(HandoverJob)
        .where(
            HandoverJob.tenant_id == claim.tenant_id,
            HandoverJob.id == claim.job_id,
            HandoverJob.state == "running",
            HandoverJob.lease_token == claim.lease_token,
            HandoverJob.lease_expires_at > func.clock_timestamp(),
        )
        .values(
            state="draft_ready",
            completed_at=func.clock_timestamp(),
            lease_token=None,
            lease_expires_at=None,
            failure_code=None,
        )
        .returning(HandoverJob.id)
        .execution_options(synchronize_session=False)
    )

    if completed_job_id is None:
        # Raising causes the enclosing transaction to roll back both inserts.
        raise HandoverLeaseLost("Lease expired before draft completion")

    return draft_id


async def save_original_and_complete_job(
    *,
    db: Database,
    claim: ClaimedJob,
    snapshot: JobExecutionSnapshot,
    retrieval: HandoverRetrieval,
    content: ValidatedHandoverContent,
    generation: GenerationMetadata,
) -> UUID:
    async with db.session() as session:
        async with session.begin():
            await session.execute(
                text(
                    "SELECT set_config("
                    "'intelligence.tenant_id', :tenant_id, true)"
                ),
                {"tenant_id": str(claim.tenant_id)},
            )

            draft_id = await persist_original_draft(
                session,
                claim=claim,
                snapshot=snapshot,
                retrieval=retrieval,
                content=content,
                generation=generation,
            )

        # Return only after the transaction commits successfully.
        return draft_id