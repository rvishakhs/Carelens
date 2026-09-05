"""Soft-delete retention sweep -- stub. Every tenant table has `deleted_at` via
TenantMixin; this job is where a real retention policy (e.g. "purge observations older
than N years for discharged residents") gets implemented once that policy is decided
and documented in governance/dpia-draft.md. Deliberately a no-op until then so nothing
is silently deleted."""

import uuid

from app.container import Container


async def run_retention_job(container: Container, care_home_ids: list[uuid.UUID]) -> None:
    # TODO: implement once a retention policy is defined.
    return None
