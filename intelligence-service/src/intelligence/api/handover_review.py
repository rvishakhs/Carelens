"""Read and append staff revisions. No clinical sign-off or source-record writes."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import AwareDatetime, Field, field_validator
from sqlalchemy import select, text

from intelligence.api.dependencies import actor, get_database
from intelligence.core.contracts import Contract, Scope
from intelligence.persistence.database import Database
from intelligence.persistence.models import EvidenceManifest, HandoverDraftVersion, HandoverJob
from intelligence.handover.contracts import HandoverSection
from intelligence.handover.prose import WARNING_LABELS, legacy_claim
from intelligence.handover.overview import overview_text

router = APIRouter(prefix="/v1/handovers", tags=["handover-review"])


class RevisionRequest(Contract):
    expected_version_id: UUID
    text: str = Field(min_length=1, max_length=20000)

    @field_validator("text")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Handover text is required")
        return value.strip()


class DraftRead(Contract):
    id: UUID
    job_id: UUID
    resident_id: UUID
    version: int
    version_kind: str
    authored_by: UUID | None
    shift_start: AwareDatetime
    shift_end: AwareDatetime
    updated_at: AwareDatetime
    text: str
    original_text: str
    warnings: list[str]
    can_edit: bool
    original_sections: tuple[HandoverSection, ...] = ()
    overview_notice: str | None = None


def draft_text(draft: HandoverDraftVersion) -> str:
    return (
        "\n\n".join(
            section["category"].replace("_", " ").capitalize()
            + "\n"
            + "\n".join(claim["text"] for claim in section["claims"])
            for section in draft.sections
        )
        if draft.version_kind == "ai_original"
        else "\n\n".join(claim["text"] for section in draft.sections for claim in section["claims"])
    )


def present(job: HandoverJob, latest: HandoverDraftVersion, original: HandoverDraftVersion) -> DraftRead:
    # Format old AI originals at read time; never reinterpret staff-authored edits.
    sections = tuple(
        HandoverSection.model_validate({
            **section,
            "claims": [{**claim, "text": legacy_claim(claim["text"])} for claim in section["claims"]],
        }) for section in original.sections
    )
    original_display = "\n\n".join(
        {"nutrition_hydration": "Nutrition & hydration", "mood_behaviour": "Mood & behaviour"}.get(
            section.category, section.category.replace("_", " ").capitalize()
        ) + "\n"
        + " ".join(claim.text for claim in section.claims)
        for section in sections
    )
    overview = overview_text(sections)
    if overview:
        attention = []
        for item in original.warnings:
            warning = item["message"]
            if warning == "source_marked_implausible":
                attention.append("A source record is flagged as implausible and requires review.")
            elif any(term in warning.lower() for term in ("ambiguous", "conflicting", "exceeds")):
                attention.append("Some recorded amounts need reconciliation; review the coverage notes.")
        if attention:
            overview = " ".join(dict.fromkeys(attention)) + "\n\n" + overview
    return DraftRead(
        id=latest.id,
        job_id=job.id,
        resident_id=job.resident_id,
        version=latest.version_number,
        version_kind=latest.version_kind,
        authored_by=latest.authored_by,
        shift_start=job.shift_start,
        shift_end=job.shift_end,
        updated_at=latest.created_at,
        text=(overview or original_display) if latest.version_kind == "ai_original" else draft_text(latest),
        original_text=original_display,
        warnings=list(dict.fromkeys(WARNING_LABELS.get(item["message"], item["message"]) for item in latest.warnings)),
        can_edit=True,
        original_sections=sections,
        overview_notice=(
            "Summary of the selected shift’s available records. See coverage notes for missing information."
        ) if overview and latest.version_kind == "ai_original" else None,
    )


def check_scope(scope: Scope, resident_id: UUID | None = None) -> None:
    # Pilot editors are the current explicitly authorised generating staff.
    # Scope is resolved afresh by CareLens, including tenant/floor/resident restrictions.
    if "handover:generate" not in scope.permissions or (
        resident_id is not None and resident_id not in scope.resident_ids
    ):
        raise HTTPException(404, "Resource unavailable")


async def set_tenant(session, scope: Scope) -> None:
    await session.execute(
        text("SELECT set_config('intelligence.tenant_id', :tenant_id, true)"),
        {"tenant_id": str(scope.tenant_id)},
    )


async def versions(session, job: HandoverJob):
    query = select(HandoverDraftVersion).where(
        HandoverDraftVersion.tenant_id == job.tenant_id,
        HandoverDraftVersion.resident_id == job.resident_id,
        HandoverDraftVersion.job_id == job.id,
    )
    latest = await session.scalar(query.order_by(HandoverDraftVersion.version_number.desc()).limit(1))
    original = await session.scalar(query.where(HandoverDraftVersion.version_kind == "ai_original"))
    if latest is None or original is None:
        raise HTTPException(409, "Draft is not available")
    return latest, original


async def scoped_job(session, scope: Scope, job_id: UUID):
    job = await session.scalar(select(HandoverJob).where(
        HandoverJob.id == job_id, HandoverJob.tenant_id == scope.tenant_id,
        HandoverJob.resident_id.in_(scope.resident_ids),
    ))
    if job is None:
        raise HTTPException(404, "Resource unavailable")
    return job


@router.get("/{job_id}/draft", response_model=DraftRead)
async def read_draft(job_id: UUID, response: Response, scope: Scope = Depends(actor),
                     database: Database = Depends(get_database)):
    response.headers["Cache-Control"] = "no-store"
    check_scope(scope)
    async with database.session() as session:
        async with session.begin():
            await set_tenant(session, scope)
            job = await scoped_job(session, scope, job_id)
            latest, original = await versions(session, job)
            return present(job, latest, original)


@router.get("/{job_id}/evidence")
async def read_evidence(job_id: UUID, response: Response, scope: Scope = Depends(actor),
                        database: Database = Depends(get_database)):
    response.headers["Cache-Control"] = "no-store"
    check_scope(scope)
    async with database.session() as session:
        async with session.begin():
            await set_tenant(session, scope)
            job = await scoped_job(session, scope, job_id)
            _, original = await versions(session, job)
            manifest = await session.scalar(select(EvidenceManifest).where(
                EvidenceManifest.id == original.manifest_id, EvidenceManifest.tenant_id == scope.tenant_id,
                EvidenceManifest.resident_id == job.resident_id, EvidenceManifest.job_id == job.id,
            ))
            if manifest is None:
                raise HTTPException(409, "Evidence is unavailable")
            history = (await session.scalars(select(HandoverDraftVersion).where(
                HandoverDraftVersion.tenant_id == scope.tenant_id, HandoverDraftVersion.job_id == job.id,
                HandoverDraftVersion.resident_id == job.resident_id,
            ).order_by(HandoverDraftVersion.version_number))).all()
            return {
                "resident_id": job.resident_id,
                "retrieved_at": manifest.retrieved_at,
                "evidence_cutoff": manifest.evidence_cutoff,
                "coverage_complete": manifest.coverage_complete,
                "sources": manifest.sources,
                "versions": [{"id": v.id, "version": v.version_number, "kind": v.version_kind,
                              "author": v.authored_by, "created_at": v.created_at, "text": draft_text(v)}
                             for v in history],
            }


@router.get("/residents/{resident_id}/latest", response_model=DraftRead | None)
async def latest_handover(
    resident_id: UUID,
    response: Response,
    scope: Scope = Depends(actor),
    database: Database = Depends(get_database),
):
    response.headers["Cache-Control"] = "no-store"
    check_scope(scope, resident_id)
    async with database.session() as session:
        async with session.begin():
            await set_tenant(session, scope)
            job = await session.scalar(
                select(HandoverJob)
                .where(
                    HandoverJob.tenant_id == scope.tenant_id,
                    HandoverJob.resident_id == resident_id,
                    HandoverJob.state == "draft_ready",
                )
                .order_by(HandoverJob.shift_end.desc(), HandoverJob.created_at.desc(), HandoverJob.id.desc())
                .limit(1)
            )
            if job is None:
                return None
            latest, original = await versions(session, job)
            return present(job, latest, original)


@router.post("/{job_id}/revisions", response_model=DraftRead)
async def save_revision(
    job_id: UUID,
    payload: RevisionRequest,
    response: Response,
    scope: Scope = Depends(actor),
    database: Database = Depends(get_database),
):
    response.headers["Cache-Control"] = "no-store"
    check_scope(scope)
    async with database.session() as session:
        async with session.begin():
            await set_tenant(session, scope)
            # Serialise edits to the same job, then compare the submitted version.
            job = await session.scalar(
                select(HandoverJob)
                .where(
                    HandoverJob.id == job_id,
                    HandoverJob.tenant_id == scope.tenant_id,
                    HandoverJob.resident_id.in_(scope.resident_ids),
                )
                .with_for_update()
            )
            if job is None:
                raise HTTPException(404, "Resource unavailable")
            if job.state != "draft_ready":
                raise HTTPException(409, "Draft is not available for editing")
            latest, original = await versions(session, job)
            if latest.id != payload.expected_version_id:
                # A retry after a lost success response must not create another revision.
                if (
                    latest.previous_version_id == payload.expected_version_id
                    and latest.authored_by == scope.actor_id
                    and draft_text(latest) == payload.text
                ):
                    return present(job, latest, original)
                raise HTTPException(409, "Draft changed; reload before saving")
            if present(job, latest, original).text == payload.text:
                return present(job, latest, original)
            revision = HandoverDraftVersion(
                id=uuid4(),
                tenant_id=job.tenant_id,
                resident_id=job.resident_id,
                job_id=job.id,
                manifest_id=original.manifest_id,
                version_number=latest.version_number + 1,
                version_kind="staff_revision",
                previous_version_id=latest.id,
                authored_by=scope.actor_id,
                # Staff prose is explicitly attributed, never presented as AI-verified citations.
                sections=[{"category": "staff_handover", "claims": [{"text": payload.text, "sources": []}]}],
                warnings=original.warnings,
                agent_version=original.agent_version,
                prompt_version=original.prompt_version,
                gateway_version=original.gateway_version,
                provider=original.provider,
                model_version=original.model_version,
                generated_at=original.generated_at,
                created_at=datetime.now(UTC),
            )
            session.add(revision)
            await session.flush()
            result = present(job, revision, original)
        return result
