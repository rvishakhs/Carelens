# Data Protection Impact Assessment (Draft)

Living document -- grows as the system is built. Sections below are seeded with
pointers into the codebase rather than restated content, so this file doesn't drift
out of sync with what's actually implemented. Fill in the narrative prose around each
pointer as each piece lands; the technical evidence itself should be pasted in close
to verbatim from the source.

**Status: draft, Phase 1 in progress. Not yet reviewed by a DPO or submitted anywhere.**

---

## 1. Nature of processing

CareLens processes care-home resident data (observations, notes, medications) to
produce shift-handover summaries for care staff. Phase 1 operates on **synthetic data
only** -- no real resident data is processed until this DPIA is further along and a
DPA is in place with a selected LLM provider (Phase 2).

## 2. Data flows

- Ingestion: `app/modules/observations/router.py` (`POST /observations`, `POST
  /observations/batch`) -- structured data validated per-type
  (`app/modules/observations/schemas.py`), free text stored verbatim then passed
  through a rule-based structurer (`app/modules/observations/adapters/rule_based_structurer.py`).
- AI processing: `app/modules/ai_gateway/service.py` -- see section 5 (pseudonymisation).
- Storage: PostgreSQL with row-level security (see section 4).
- Access: web handover view (`app/modules/handover/`), read-only in Phase 1.

## 3. Legal basis / consent

Resident consent flags exist on the `residents` model
(`app/modules/residents/models.py`: `data_processing_consent`, `photo_consent`) but
Phase 1 does not yet gate any processing on them -- **TODO before Phase 1 is done**:
decide and implement what happens when `data_processing_consent` is false.

Family access is explicitly deferred to Phase 5 pending consent machinery
(`app/modules/identity/permissions.py`: `Role.FAMILY` has an empty permission set).

## 4. Row-Level Security (technical control evidence)

Pattern and rationale: `migrations/README.md`. Runtime enforcement:
`app/shared/database.py` (`rls_session()` docstring explains the zero-rows-by-default
property). Test evidence goes here once `tests/rbac/test_rls_isolation.py` is
implemented against a real Postgres instance -- currently skipped, tracked as a
blocker.

## 5. Pseudonymisation (AI gateway)

Design: `app/modules/ai_gateway/pseudonymiser.py` docstring + `app/modules/ai_gateway/service.py`
(the pseudonymise -> LLM -> re-identify flow). Known gap, tracked in
`governance/hazard-log.md` H-003: no NER pass yet, regex-only PII stripping. Test
evidence: `tests/unit/test_pseudonymiser.py` -- currently a starter suite, not the
full edge-case fixture the design calls for.

**Do not select a real LLM provider for anything beyond gateway-path testing (dev
keys, synthetic data only) until H-003 is closed.**

## 6. RBAC matrix (technical control evidence)

Full matrix: `app/modules/identity/permissions.py` (`ROLE_PERMISSIONS`). Structural
tests: `tests/rbac/test_permission_matrix.py`. The endpoint x role sweep proving the
matrix matches actual route behaviour is a TODO in that file, blocked on the same
Postgres/migrations dependency as section 4.

## 7. Audit trail

Design: `app/modules/audit/` -- append-only at the DB layer (grants + trigger, see
`migrations/README.md`), subscribes to domain events
(`app/modules/audit/module.py`) including `RecordViewed` (every handover page view is
itself audited -- see `app/modules/handover/service.py`). Export is itself audited
(`app/modules/audit/router.py`).

## 8. Retention

Soft delete (`deleted_at`) exists on every tenant table via `TenantMixin`
(`app/shared/database.py`). Actual retention policy (how long, what triggers purge)
is **not yet decided** -- `workers/jobs/retention_job.py` is a deliberate no-op stub
until it is.

## 9. Open items before this DPIA can be considered complete

1. Consent-gating decision (section 3).
2. NER pseudonymisation pass + full fixture suite (section 5 / hazard-log H-003).
3. RLS + RBAC test evidence against real Postgres (sections 4, 6).
4. Retention policy decision (section 8).
5. LLM provider selection + DPA review (Phase 2, out of Phase 1 scope by design).
