import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from intelligence.core.errors import ExecutionAuthorisationDenied, ExecutionAuthorisationUnavailable
from intelligence.handover.authorization import (
    CareLensAuthorityReader,
    CareLensExecutionAuthorizer,
    ServiceGrant,
    StaffGrant,
)
from intelligence.persistence.job_repository import JobExecutionSnapshot


@pytest.fixture
def setup_authority():
    now = datetime.now(UTC)
    job = JobExecutionSnapshot(
        job_id=uuid4(), tenant_id=uuid4(), resident_id=uuid4(),
        initiating_actor_id=uuid4(), service_identity="handover-worker",
        trigger="manual", purpose="handover_generation",
        shift_start=now - timedelta(hours=12), shift_end=now, timezone="Europe/London",
    )
    reader = AsyncMock(spec=CareLensAuthorityReader)
    reader.service_grant.return_value = ServiceGrant(
        job.tenant_id, job.service_identity, frozenset({job.resident_id, uuid4()}),
        frozenset({"handover:generate", "handover:schedule"}),
    )
    reader.staff_grant.return_value = StaffGrant(
        job.tenant_id, job.initiating_actor_id, frozenset({job.resident_id}),
        frozenset({"handover:generate", "staff:only"}),
    )
    reader.resident_eligible.return_value = True
    authorizer = CareLensExecutionAuthorizer(reader, expected_service_identity="handover-worker")
    return job, reader, authorizer


def test_manual_context_is_narrowed_to_current_shared_permissions(setup_authority):
    job, reader, authorizer = setup_authority
    context = asyncio.run(authorizer.authorise(job=job))
    assert context.permissions == frozenset({"handover:generate"})
    assert context.authorised_resident_ids == frozenset({job.resident_id})
    reader.staff_grant.assert_awaited_once_with(
        tenant_id=job.tenant_id, actor_id=job.initiating_actor_id,
    )


@pytest.mark.parametrize("grant_name,field,value", [
    ("service_grant", "tenant_id", uuid4()),
    ("service_grant", "service_identity", "another-service"),
    ("service_grant", "resident_ids", frozenset()),
    ("service_grant", "permissions", frozenset()),
    ("staff_grant", "tenant_id", uuid4()),
    ("staff_grant", "actor_id", uuid4()),
    ("staff_grant", "resident_ids", frozenset()),
    ("staff_grant", "permissions", frozenset()),
])
def test_revoked_or_mismatched_grants_are_denied(setup_authority, grant_name, field, value):
    job, reader, authorizer = setup_authority
    method = getattr(reader, grant_name)
    method.return_value = replace(method.return_value, **{field: value})
    with pytest.raises(ExecutionAuthorisationDenied):
        asyncio.run(authorizer.authorise(job=job))
    reader.resident_eligible.assert_not_awaited()


@pytest.mark.parametrize("eligible", [False, None, "true", 1])
def test_eligibility_must_be_explicit_true(setup_authority, eligible):
    job, reader, authorizer = setup_authority
    reader.resident_eligible.return_value = eligible
    with pytest.raises(ExecutionAuthorisationDenied):
        asyncio.run(authorizer.authorise(job=job))


def test_scheduled_requires_permission_and_never_impersonates_staff(setup_authority):
    job, reader, authorizer = setup_authority
    job = replace(job, trigger="scheduled", initiating_actor_id=None)
    context = asyncio.run(authorizer.authorise(job=job))
    assert context.initiating_actor_id is None
    reader.staff_grant.assert_not_awaited()
    reader.service_grant.return_value = replace(
        reader.service_grant.return_value, permissions=frozenset({"handover:generate"}),
    )
    with pytest.raises(ExecutionAuthorisationDenied):
        asyncio.run(authorizer.authorise(job=job))


@pytest.mark.parametrize("changes", [
    {"service_identity": "forged"}, {"purpose": "other"}, {"trigger": "unknown"},
    {"initiating_actor_id": None}, {"trigger": "scheduled"},
])
def test_invalid_job_is_denied_before_authority_lookup(setup_authority, changes):
    job, reader, authorizer = setup_authority
    with pytest.raises(ExecutionAuthorisationDenied):
        asyncio.run(authorizer.authorise(job=replace(job, **changes)))
    reader.service_grant.assert_not_awaited()


@pytest.mark.parametrize("failure", [ExecutionAuthorisationUnavailable(), TimeoutError()])
def test_unavailable_authority_stops_execution(setup_authority, failure):
    job, reader, authorizer = setup_authority
    reader.service_grant.side_effect = failure
    with pytest.raises(ExecutionAuthorisationUnavailable):
        asyncio.run(authorizer.authorise(job=job))
    reader.staff_grant.assert_not_awaited()
    reader.resident_eligible.assert_not_awaited()
