# Handover workflow wiring

## Implemented in this increment

- The resident screen obtains the last four completed shifts from the server,
  submits the selected shift with a stable per-attempt idempotency key, and polls
  the job. It loads that exact job's draft, including when an older shift was selected.
- Original claim references, coverage metadata and immutable version history are
  available to currently authorised resident reviewers. Source IDs are references,
  not links to a historical clinical snapshot.
- Beat reconciles completed shifts every 60 seconds on a dedicated scheduling queue,
  keeping longer scheduling sweeps separate from lease recovery.
  With scheduling enabled, shifts ending at 07:00 and 19:00 Europe/London become
  eligible on the next sweep. This is minute-level scheduling, not exact-second delivery.
- Missed runs catch up over the last four shifts by default (configurable 1–14).
  Longer outages require deliberate manual submission. Enabling scheduling for
  the first time also processes this catch-up window.
- Fresh service scope, scheduling permission and resident eligibility are checked.
  Execution rechecks permissions independently. Scheduled jobs do not impersonate staff.
- Manual and scheduled submissions share a per-tenant/resident transaction lock,
  the same unique shift identity, and transactional job/outbox creation.
  A failed existing job is reused, not silently replaced by a new generation.

## Local activation

Keep existing secrets in the untracked environment file. Configure the existing
database, CareLens URL, service credentials, service identity and
`INTELLIGENCE_DISPATCHER_TENANT_IDS`. CareLens must explicitly grant
`handover:generate` and `handover:schedule` and enrol the residents.

Set `INTELLIGENCE_SCHEDULE_ENABLED=true` only when automatic generation is intended;
it can cause provider calls. `INTELLIGENCE_SCHEDULE_CATCH_UP_SHIFTS=4` controls the
bounded lookback. Scheduling defaults off. No live settings were changed by this increment.

Start/rebuild the existing `handover` Compose profile (API, dispatcher, worker,
recovery-worker, scheduling-worker, Beat, Redis). PostgreSQL and CareLens remain separately configured.
Restart the frontend development server if the intelligence proxy is not yet active.
Production still requires the same-origin `/intelligence` reverse proxy.

## Remaining implementation boundaries

This increment does not establish clinical sign-off. CareLens currently has a
handover read model, but no finalisation record, nurse-in-charge designation or
signed-version write contract. Implement those together with immutable final
versions, concurrency control against edits, audit, and reliable cross-service
delivery. Do not label a saved staff revision as finalised.

Source pagination is not snapshot-consistent. Coverage stays explicitly incomplete.
Corrections/deletions and late records need a source revision/checkpoint contract,
plus an explicit regeneration/amendment policy. Cross-source event linkage is also
needed before semantic deduplication can be claimed.

Free-text privacy remains fail-closed and generation remains extractive. Do not
enable arbitrary raw clinical text or weaken validation as a wiring shortcut.
Narrative output needs an approved text-minimisation pipeline and evaluated support
checks. Clinical and privacy acceptance remain separate from software tests.

## Verification

Run the offline intelligence suite and frontend TypeScript checks. Database
integration tests are opt-in. A running-service test must still prove actual
CareLens authentication, PostgreSQL persistence, Redis delivery, provider access,
recovery, concurrent edits and tenant isolation with synthetic data.
