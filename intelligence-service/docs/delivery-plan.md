# Delivery plan and gates

## Milestone 0 — independent runnable skeleton (this change)

- [x] Separate package/configuration/container/API on port 8100.
- [x] Versioned typed contracts, registry and controlled dependencies.
- [x] Synthetic source reader and fake-only gateway path.
- [x] History/demo handover results with source references, bounded memory and access checks.
- [x] Isolated tests and architecture/extension documentation.
- [ ] Promote folder into its own Git repository when its location/remote are selected; no remote or nested repo created here.

This demonstrates module boundaries and local request flow. It does not complete Phase 1 production identity/durability or the full pilot.

## Milestone 1 — identity and live read contract

CareLens work:

- Introduce read-only care-event permission and resident/event detail route.
- Expose complete period history with stable pagination, source versions and trustworthy completeness checkpoints.
- Distinguish effective time, entered time, date precision and recorded-time fallback.
- Establish service identity plus delegated staff scope, audience verification and timely revocation handling.

Intelligence work:

- Add OIDC/JWKS adapter with issuer/audience/expiry verification, service/delegation binding and fail-closed scope resolution. Do not translate the demo bearer token into a production service key with client-supplied tenants.
- Implement HTTPX connector with bounded timeouts and scoped credentials. Adapter contracts use the actual CareLens routes; do not invent working APIs.
- Map 14 clinical sources plus care events; explicitly exclude generic native observations/medications/appointments until scope changes.
- Handle unavailable/truncated feeds and date-only precision; validate offered/consumed quantities, incremental/cumulative intake and source linkage.

Gate: synthetic records through real CareLens APIs preserve provenance; cross-tenant/floor/resident and revocation tests pass. No real model needed.

## Milestone 2 — evidence persistence and change ingestion

- Introduce separate PostgreSQL database and Alembic migrations; least-privilege runtime role and tenant RLS on all derived stores.
- Define source record, evidence manifest, result version and checkpoint schemas with unique composite source identities.
- Add CareLens transactional outbox, idempotent ingestion and snapshot reconciliation.
- Prove correction/deletion, out-of-order events, pagination under concurrent writes and lag measurement.
- Implement scoped expiry/deletion with legal/incident hold handling and backup-restore reconciliation.

Gate: replay/restart loses no committed source change, repeat delivery does not duplicate records, and stale/deleted/restricted evidence cannot be served as current.

## Milestone 3 — durable workflows and workers

- Add Temporal adapter and separately executable worker; keep the API fast by returning 202 + durable run ID.
- Activities receive IDs/scopes, not raw clinical text in durable history. Retrieve content within authorised activities; assess payload encryption and history retention.
- Establish bounded retries, deadlines, cancellation, idempotency and per-job cost reservations.
- Persist queued/running/failed/awaiting-review states; recover after process termination and replay.

Gate: kill/restart a worker mid-run; observe one coherent job and no duplicate external command. The current synchronous 200 contract evolves explicitly to a versioned asynchronous API; do not silently change client assumptions.

## Milestone 4 — real gateway and resident search

- Build local free-text minimisation/entity handling for notes, questions and conversation context; preserve clinical time/units and inspect outbound payloads.
- Separate encrypted alias mapping access from provider egress; validate output references and re-identify only in current authorised context.
- Select model/embedding deployments against the agreed quality, cost and approved-region criteria after P0-06 requirements are settled.
- Add structured retrieval plus full-text/pgvector candidate fusion. Enforce access filters before retrieval, reranking, prompt construction and display.
- Run all relevant revised S01–S20 cases, variants and held-out synthetic questions. S15 pagination remains a required gate even though its walkthrough was deferred.

Gate: cited resident enquiry meets the agreed accuracy/privacy targets; measure latency/cost/freshness, retain failures and compare actual results to targets. No model/provider has been selected by the skeleton.

## Milestone 5 — handover review integration

- Generate by explicit shift, timezone and resident roster; use complete evidence and deterministic metrics.
- Persist immutable original AI draft, attributed staff revisions and linked CareLens final artefact separately.
- Only the designated nurse in charge can finalise after current permission, source freshness and version checks; managers/senior carers can edit within scope but do not gain sign-off by their role.
- Preserve final/original evidence under the care home's official record policy; 30-day abandoned-draft expiry does not delete signed evidence.
- Support reviewed amendments, late-record flags, concurrent-edit conflicts and manual fallback when no nurse in charge is available.

Gate: H01–H10 and nurse walkthrough pass; no automatic signing. Glenrose reviews actual outputs; technical owner validates hidden access/gateway/persistence properties.

## Milestone 6 — controlled pilot and extensions

- Resolve remaining P0-06 controller/privacy/clinical responsibilities, UK nation/regions, eligibility and retention details before real-data activation.
- Record operational owner, incident response, dashboards, backup restore, rollback, deployment configuration and support access.
- Benchmark at five concurrent staff, 1,000 records/30-day enquiry and 20 residents/2,000-record handover envelope. Targets: p95 10s search/60s handover/60s ingestion and average model costs £0.05/£0.50.
- Compare manual and AI-assisted review using Glenrose's case feedback; investigate failures rather than averaging away disclosure or clinical omissions.
- Add analytics, confirmed tasks/reminders, voice, reviewed communications and clinically validated detection in separate feature milestones; use the extension guide.

No dates are promised for later milestones: estimate them after the first live API contract and worker restart proof. At each gate, record changed scope, evidence, unresolved risks and owners.

## Cloud decision checklist

AWS and Azure remain options, not deployed resources. Select based on approved processing regions, model/embedding availability, private networking, managed PostgreSQL extension support, secret management, support/subprocessor access, retention/backup options and total cost. Temporal deployment (managed or self-hosted) needs its own history/payload region assessment. Keep application and intelligence credentials/databases independent whichever cloud is selected.

## Current unresolved product details

- Confirm the S17 comment interpretation: five minutes later, another 50 ml. Synthetic examples currently state that assumption explicitly.
- Obtain the approved post-fall monitoring protocol before adding monitoring behaviour; the 48-hour view is evidence retrieval only.
- Final official record retention, derived retrieval horizon, alias retry lifetime and holds need operational confirmation.
- Detailed per-job cost caps, timeout/retry and usability/sample-size proposals remain to be confirmed; headline P0-08 targets and reviewers are already agreed.
