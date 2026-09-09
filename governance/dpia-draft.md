# Data Protection Impact Assessment (Draft)

Living document -- grows as the system is built. Sections below are seeded with
pointers into the codebase rather than restated content, so this file doesn't drift
out of sync with what's actually implemented. Fill in the narrative prose around each
pointer as each piece lands; the technical evidence itself should be pasted in close
to verbatim from the source.

**Status: draft, Phase 1 in progress. Not yet reviewed by a DPO or submitted anywhere.**

**9 September 2026 update:** the original phase labels below describe the earlier
application roadmap. The separate intelligence pilot now has an agreed
[P0-05 specification](../docs/phase-0/pilot-specification.md) and a draft
[P0-06 data-policy addendum](intelligence-pilot-data-policy.md). The addendum
extends this DPIA with the 14 clinical sources plus care events, recipients,
processing locations, retention proposals and intended use. The pilot country is
confirmed as the United Kingdom. CareLens is currently local-only; future AWS or
Azure hosting and exact regions remain undecided. A separate intelligence layer
with a mandatory [AI gateway](intelligence-ai-gateway-design.md) is the agreed
direction. Accountable owners and remaining policy approval are outstanding. No real-data
activation or technical control implementation is established by these documents.

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
`app/shared/database.py` (`rls_session()` documents scoped sessions). Updated
evidence: `tests/integration/test_clinical_observation_feed.py` exercises the 14
clinical sources and native storage against PostgreSQL under a non-superuser
application role, including tenant/floor denial. See the
[clinical mapping report](../docs/phase-0/clinical-feed-resolution.md). Broader
endpoint/role coverage and the future intelligence service still need validation.

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
matrix matches actual route behaviour remains broader work; the clinical feed
integration evidence in section 4 covers a bounded subset. Live grants are
DB-backed and cached, so seed-role tests alone do not prove runtime revocation.

## 7. Audit trail

Design: `app/modules/audit/` -- append-only at the DB layer (grants + trigger, see
`migrations/README.md`), subscribes to domain events
(`app/modules/audit/module.py`) including `RecordViewed` (every handover page view is
itself audited -- see `app/modules/handover/service.py`). Export is itself audited
(`app/modules/audit/router.py`).

## 8. Retention

Many records expose soft deletion; it is not a purge policy. On 9 September 2026
the user agreed product defaults: session-only conversations with a 24-hour
server-side maximum, unfinalised drafts after 30 days without activity (subject to
review/hold), and operational audit metadata for 90 days. Temporary gateway
mappings expire after processing and permitted retries; derived data remains only
while needed and follows source changes. Finalised handovers and signed-review
history follow the care home's approved record schedule. Exact derived-data
horizon, retry/hold limits, official record periods and other details remain open.
`app/workers/jobs/retention_job.py` remains a deliberate no-op stub; no deletion
controls were implemented by the agreement. See the
[P0-06 addendum](intelligence-pilot-data-policy.md#4-retention-schedule--agreed-defaults-and-remaining-decisions)
for agreed defaults, unapproved proposals and responsible-owner validation.

## 9. Open items before this DPIA can be considered complete

1. Consent-gating decision (section 3).
2. NER pseudonymisation pass + full fixture suite (section 5 / hazard-log H-003).
3. RLS + RBAC test evidence against real Postgres (sections 4, 6).
4. Retention policy decision (section 8).
5. LLM provider selection + DPA review (Phase 2, out of Phase 1 scope by design).
