# Resident handover review

The resident Overview shows AI insights between At a Glance and Vitals. The card
loads the newest completed handover by shift end. An old shift is labelled with
its dates; it is never presented as today's summary. Missing metrics show dashes,
not invented scores. No draft, access denial and service errors have separate states.

## Read/save endpoints

- GET `/v1/handovers/residents/{resident_id}/latest`: newest available draft, original
  AI text, warnings, version and author information; JSON null when none exists.
- POST `/v1/handovers/{job_id}/revisions`: `expected_version_id` and `text`.
  Appends an immutable staff revision, preserving the AI original and manifest.
  Stale versions return 409. Retrying the identical most recent edit by the same
  author returns that revision. It never finalises a handover or updates care records.

Both routes use the current CareLens staff scope. Pilot editing follows the
existing explicit generating-staff allowlist and `handover:generate` permission,
including tenant/floor/resident access. This does not grant finalisation rights.
Staff revisions are visibly labelled with author ID and time; edited prose does
not inherit AI-verified citations. Original structured citations remain stored.
Existing draft-version tables are used, so no migration is needed.

## Local and deployed routing

The browser sends its existing staff bearer token through the same-origin
`/intelligence` prefix. Vite proxies this to `http://127.0.0.1:8100`, stripping the
prefix. Restart Vite if needed after changing its config. Run the intelligence
API on port 8100 with its PostgreSQL and CareLens identity settings configured.
The generation control lists server-calculated completed shifts and submits an
explicit Generate now request. It polls job status and opens that exact draft.
Loading the card or its review dialog does not call the model.

Reviewers can inspect original claim references and version history. References
identify source records and versions; historical source-record content and direct
source links are not implemented. See [workflow wiring](handover-workflow-wiring.md)
for scheduled submission and the remaining finalisation and coverage boundaries.

For deployment configure the application's reverse proxy with the same prefix
mapping to the intelligence API, forwarding Authorization and preserving no-store
response headers. Do not forward this route to an untrusted external host.
The Vite dev proxy is not part of the production static build.

## Verification

Frontend TypeScript/Vite build and API unit tests cover the change. A temporary
synthetic browser harness verified the card, dialog, edit/save and original-text
preservation UI; it was removed afterward. Live authenticated PostgreSQL persistence
still needs an end-to-end check with an existing draft. There are no localStorage
copies of resident summaries or UI-only save success fallbacks.
