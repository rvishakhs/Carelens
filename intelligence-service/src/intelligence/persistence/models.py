from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from intelligence.persistence.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class HandoverJob(TimestampMixin, Base):
    __tablename__ = "handover_jobs"

    __table_args__ = (
        # Supports tenant-safe foreign keys from other tables.
        ForeignKeyConstraint(
            [
                "tenant_id",
                "resident_id",
                "shift_start",
                "shift_end",
                "previous_job_id",
            ],
            [
                "handover_jobs.tenant_id",
                "handover_jobs.resident_id",
                "handover_jobs.shift_start",
                "handover_jobs.shift_end",
                "handover_jobs.id",
            ],
            name=("handover_jobs_tenant_id_resident_id_shift_start_shift_end__fkey"),
        ),
        UniqueConstraint(
            "tenant_id",
            "id",
            name="handover_jobs_tenant_id_id_key",
        ),
        UniqueConstraint(
            "tenant_id",
            "resident_id",
            "id",
            name="handover_jobs_tenant_id_resident_id_id_key",
        ),
        UniqueConstraint(
            "tenant_id",
            "resident_id",
            "shift_start",
            "shift_end",
            "id",
            name="handover_jobs_tenant_id_resident_id_shift_start_shift_end_i_key",
        ),
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="handover_jobs_tenant_id_idempotency_key_key",
        ),
        UniqueConstraint(
            "tenant_id",
            "resident_id",
            "shift_start",
            "shift_end",
            "generation_number",
            name="handover_jobs_tenant_id_resident_id_shift_start_shift_end_g_key",
        ),
        CheckConstraint(
            "length(idempotency_key) > 0",
            name="nonempty_idempotency_key",
        ),
        CheckConstraint(
            "shift_end > shift_start",
            name="valid_shift",
        ),
        CheckConstraint(
            "generation_number > 0",
            name="positive_revision",
        ),
        CheckConstraint(
            "purpose = 'handover_generation'",
            name="valid_purpose",
        ),
        CheckConstraint(
            "trigger_type IN ('manual', 'scheduled')",
            name="valid_trigger",
        ),
        CheckConstraint(
            "state IN ('queued', 'running', 'draft_ready', 'failed', 'cancelled')",
            name="valid_state",
        ),
        CheckConstraint(
            "attempts >= 0",
            name="nonnegative_attempts",
        ),
        CheckConstraint(
            "max_attempts > 0",
            name="positive_max_attempts",
        ),
        CheckConstraint(
            "length(timezone) > 0 AND length(service_identity) > 0",
            name="required_execution_context",
        ),
        CheckConstraint(
            "trigger_type <> 'manual' OR requested_by IS NOT NULL",
            name="manual_request_has_actor",
        ),
        # A running job must have a worker lease.
        CheckConstraint(
            "(state = 'running') = (lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="running_has_lease",
        ),
        CheckConstraint(
            "(lease_token IS NULL) = (lease_expires_at IS NULL)",
            name="lease_fields_paired",
        ),
        # A terminal job must have a completion timestamp.
        CheckConstraint(
            "(state IN ('draft_ready', 'failed', 'cancelled')) = (completed_at IS NOT NULL)",
            name="completion_matches_state",
        ),
        # Only subsequent generations reference a previous job.
        CheckConstraint(
            "(generation_number = 1 AND previous_job_id IS NULL) OR "
            "(generation_number > 1 AND previous_job_id IS NOT NULL)",
            name="generation_has_predecessor",
        ),
        CheckConstraint(
            "previous_job_id IS NULL OR previous_job_id <> id",
            name="previous_job_not_self",
        ),
        Index(
            "ix_handover_jobs_dispatch",
            "tenant_id",
            "state",
            "next_attempt_at",
        ),
        Index(
            "ix_handover_jobs_lease",
            "tenant_id",
            "lease_expires_at",
            postgresql_where=text("state = 'running'"),
        ),
        Index(
            "ix_handover_jobs_resident",
            "tenant_id",
            "resident_id",
            text("shift_end DESC"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )

    # CareLens identities: no cross-database foreign keys.
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )

    resident_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )

    requested_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )

    trigger_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    shift_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    shift_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    generation_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )

    state: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'queued'"),
    )

    # Store a controlled code, never a raw exception or clinical text.
    failure_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Worker ownership and recovery.
    lease_token: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Execution timestamps.
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    timezone: Mapped[str] = mapped_column(Text, nullable=False)

    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    service_identity: Mapped[str] = mapped_column(Text, nullable=False)

    purpose: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'handover_generation'"),
    )

    # Generation history.
    previous_job_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )

    # Retry tracking.
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("3"))

    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class DispatchOutbox(TimestampMixin, Base):
    __tablename__ = "dispatch_outbox"

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "job_id"],
            ["handover_jobs.tenant_id", "handover_jobs.id"],
            name="dispatch_outbox_tenant_id_job_id_fkey",
        ),
        UniqueConstraint(
            "tenant_id",
            "job_id",
            "dispatch_number",
            name="dispatch_outbox_tenant_id_job_id_dispatch_number_key",
        ),
        CheckConstraint(
            "dispatch_number > 0",
            name="positive_dispatch_number",
        ),
        CheckConstraint(
            "task_name = 'intelligence.handover.generate'",
            name="valid_task_name",
        ),
        CheckConstraint(
            "state IN ('pending', 'publishing', 'published')",
            name="valid_state",
        ),
        CheckConstraint(
            "attempts >= 0",
            name="nonnegative_attempts",
        ),
        CheckConstraint(
            "(state = 'publishing') = (lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="publishing_has_lease",
        ),
        CheckConstraint(
            "(lease_token IS NULL) = (lease_expires_at IS NULL)",
            name="lease_fields_paired",
        ),
        CheckConstraint(
            "(state = 'published') = (published_at IS NOT NULL)",
            name="publication_matches_state",
        ),
        Index(
            "ix_dispatch_outbox_due",
            "tenant_id",
            "state",
            "available_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )

    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )

    dispatch_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )

    task_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'intelligence.handover.generate'"),
    )

    state: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'pending'"),
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    lease_token: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )

    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    failure_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "job_id"],
            ["handover_jobs.tenant_id", "handover_jobs.id"],
            name="fk_idempotency_tenant_job",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "length(idempotency_key) > 0",
            name="nonempty_idempotency_key",
        ),
        CheckConstraint(
            "length(request_fingerprint) = 64",
            name="sha256_fingerprint_length",
        ),
        Index(
            "ix_idempotency_tenant_job",
            "tenant_id",
            "job_id",
        ),
    )

    # Composite primary key provides the required uniqueness.
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )

    actor_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    # SHA-256 hex digest of the canonical, normalized request.
    request_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class EvidenceManifest(Base):
    __tablename__ = "evidence_manifests"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "id",
            name="evidence_manifests_tenant_id_id_key",
        ),
        UniqueConstraint(
            "tenant_id",
            "resident_id",
            "job_id",
            "id",
            name="evidence_manifests_tenant_id_resident_id_job_id_id_key",
        ),
        UniqueConstraint(
            "tenant_id",
            "job_id",
            "attempt_token",
            name="evidence_manifests_tenant_id_job_id_attempt_token_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "resident_id", "job_id"],
            [
                "handover_jobs.tenant_id",
                "handover_jobs.resident_id",
                "handover_jobs.id",
            ],
            name="evidence_manifests_tenant_id_resident_id_job_id_fkey",
        ),
        CheckConstraint(
            "jsonb_typeof(sources) = 'array'",
            name="sources_is_array",
        ),
        CheckConstraint(
            "jsonb_typeof(warnings) = 'array'",
            name="warnings_is_array",
        ),
        Index(
            "ix_evidence_manifests_job",
            "tenant_id",
            "job_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    resident_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    job_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    attempt_token: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    evidence_cutoff: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    coverage_complete: Mapped[bool] = mapped_column(Boolean, nullable=False)

    source_checkpoint: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True), nullable=True)

    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)

    warnings: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class HandoverDraftVersion(Base):
    __tablename__ = "handover_draft_versions"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "job_id",
            "id",
            name="handover_draft_versions_tenant_id_job_id_id_key",
        ),
        UniqueConstraint(
            "tenant_id",
            "job_id",
            "version_number",
            name="handover_draft_versions_tenant_id_job_id_version_number_key",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "resident_id", "job_id", "manifest_id"],
            [
                "evidence_manifests.tenant_id",
                "evidence_manifests.resident_id",
                "evidence_manifests.job_id",
                "evidence_manifests.id",
            ],
            name=("handover_draft_versions_tenant_id_resident_id_job_id_manif_fkey"),
        ),
        ForeignKeyConstraint(
            ["tenant_id", "job_id", "previous_version_id"],
            [
                "handover_draft_versions.tenant_id",
                "handover_draft_versions.job_id",
                "handover_draft_versions.id",
            ],
            name=("handover_draft_versions_tenant_id_job_id_previous_version__fkey"),
        ),
        CheckConstraint(
            "version_number > 0",
            name="positive_version_number",
        ),
        CheckConstraint(
            "version_kind IN ('ai_original', 'staff_revision')",
            name="valid_version_kind",
        ),
        CheckConstraint(
            "(version_kind = 'ai_original' "
            "AND version_number = 1 "
            "AND previous_version_id IS NULL) "
            "OR "
            "(version_kind = 'staff_revision' "
            "AND version_number > 1 "
            "AND previous_version_id IS NOT NULL "
            "AND authored_by IS NOT NULL)",
            name="valid_version_history",
        ),
        CheckConstraint(
            "previous_version_id IS NULL OR previous_version_id <> id",
            name="previous_version_not_self",
        ),
        CheckConstraint(
            "jsonb_typeof(sections) = 'array'",
            name="sections_is_array",
        ),
        CheckConstraint(
            "jsonb_typeof(warnings) = 'array'",
            name="warnings_is_array",
        ),
        Index(
            "uq_handover_original",
            "tenant_id",
            "job_id",
            unique=True,
            postgresql_where=text("version_kind = 'ai_original'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    resident_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    job_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    manifest_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    version_kind: Mapped[str] = mapped_column(Text, nullable=False)

    previous_version_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    authored_by: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    sections: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)

    warnings: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )

    agent_version: Mapped[str] = mapped_column(Text, nullable=False)

    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)

    gateway_version: Mapped[str] = mapped_column(Text, nullable=False)

    provider: Mapped[str] = mapped_column(Text, nullable=False)

    model_version: Mapped[str] = mapped_column(Text, nullable=False)

    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
