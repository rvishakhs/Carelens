# Readable handover prose

The old provider prompt required copying JSON into each claim and the validator
rejected any other wording. Changing a UI label or asking the model to summarise
would not fix that contract.

The supported-prose-v2 contract builds readable statements from already minimised
evidence in trusted code, supplies those approved statements and source aliases to
the provider, and verifies exact statements and citations on return. Grouped care
sections form the review draft. The model cannot add conclusions or recalculate
totals. This is constrained, evidence-backed prose, not unrestricted clinical
narrative synthesis.

- Fluid estimates remain estimates and are not included in exact consumption totals.
- Qualitative meal amounts remain qualitative.
- Care-event duration is not asserted to be walking or wandering duration.
- False template classifiers do not become negative clinical findings.
- Declined/refused/not-applicable care does not imply selected care was delivered.
- Missing, date-only and unknown-time evidence retains its qualifications.
- Coverage remains incomplete until source snapshot/coverage contracts are implemented.

API presentation also formats recognised legacy AI claim text and warning codes.
It does not update stored drafts or reinterpret staff-authored revisions. Version
history retains the exact original text for audit. Existing drafts therefore become
readable after API restart and refresh, without a new model call. New generations
persist readable prose and record the new prompt/gateway versions. Restart both API
and handover workers to use the updated pipeline. There is no database migration.

Tests cover the sample's fluid, meal, mobility and behaviour facts; omitted/negative
fields, refusal, unknown times, partial totals, immutable originals and staff prose.
Provider requests are tested with mock transport; no live provider validation or
clinical acceptance is claimed.

## Main shift overview

The review API now derives a concise overview for recognised care-event statements.
It summarises meal/drink participation, walking support and recorded behaviour
instead of repeating each event's time, duration and quantity. The reporting window
remains the selected 12-hour shift. It does not infer daily patterns outside that window.

Original detailed claims and citations stay in the evidence panel and stored version
history. Staff edits are never automatically summarised. Coverage notes are expandable
below the main text; flagged implausibility and reconciliation issues also remain in
the overview. No migration, re-generation or extra provider call is needed for existing
AI originals: restart the API and refresh the frontend.

Only recognised canonical care-event statements are condensed. Unrecognised text,
refused care, incidents and uncertain event times remain visible rather than being
silently removed. This is not an all-domain risk detector: no thresholds, resident
baselines or clinical risk scores have been introduced. "Normal", "adequate intake"
and "no concerns" are not inferred from absent records or withheld free-text notes.

The overview is now one flowing paragraph. When every recognised drink has an
estimate and source IDs are unique, it sums those estimates with Decimal arithmetic
and labels the result approximate and limited to recorded drinks. Missing estimates
or duplicate sources prevent this calculation. Exact fluid metrics remain unchanged.

Mapping version care-events-v2 adds controlled flags for sandwich, medium portion,
tea, medium walking distance and unknown trigger. Two exact whole-note garden
phrases can map to a location flag; names, negation or extra context prevent that
mapping. This does not enable arbitrary free-text processing. These new details
require fresh evidence retrieval: existing immutable drafts cannot recover fields
that were withheld. Normal resubmission of the same shift still reuses the existing
job; this change does not add regeneration or rewrite stored drafts.
