# Care-event handover integration

The worker now reads two feeds: existing clinical observations (calendar-expanded
for date-only sources) and care events (exact half-open shift interval).
`GET /internal/intelligence/care-events` uses the same service token, pilot resident
eligibility and tenant/floor RLS as the internal observation endpoint. Parameters:
`tenant_id`, `resident_id`, `since`, `until`, `limit` (1–500), `offset` (non-negative).
No migration or copying historical data is required. The staff `/observations`
endpoint is unchanged; care events remain available in care-recording history.

Care-event responses use the observation transport envelope with source_type
`care_events`, type `note`, and recorded_at containing occurred_at. The internal
value includes actual created/updated times, template/category IDs and names,
section-qualified option IDs/codes/labels, and typed measurements. Child aggregates
avoid row multiplication. Ordering is occurred_at then ID. Deleted events and
residents are excluded. Template metadata is current, not a historical snapshot;
its modification timestamps participate in the evidence fingerprint.

The connector validates resident/time/source and traverses through an empty page.
Duplicates, invalid responses, exhausted page limits or later-page failures reject
the entire retrieval. Offset pagination is not snapshot consistent; coverage stays
incomplete. The backend window excludes the end timestamp. All event statuses are
preserved, but declined/refused/not-applicable events produce no intake amounts.

Mapping version `care-events-v1` recognises known drink/meal template names and
mobility/emotional-support categories. Unknown categories remain generic evidence
with reviewer warnings. Renaming configurable templates can therefore reduce
mapping coverage; stable machine-code configuration should replace this pilot map
before expanding it. Raw options and measurements remain internal, fingerprinted
evidence; arbitrary labels, names, notes and summaries never cross the gateway.
Only explicitly mapped numeric/boolean fields are rendered. Unmapped fields and
free text are withheld with warnings, not interpreted as absent clinical findings.

For 150 ml offered / Half and 280 ml offered / All: offered subtotal is 430 ml;
per-event estimated consumption is 75 and 280 ml. These estimates are explicitly
labelled and do not populate exact consumed metrics. "Most" is qualitative, not an
invented percentage. Ambiguous legacy Volume measurements remain uninterpreted.
Current separate sources have no shared event linkage: do not duplicate the same
care into both event and clinical tables; cross-source semantic deduplication is
not established.

Restart CareLens and the intelligence worker after deployment. Test one completed,
previously unsubmitted shift. Existing drafts do not change, and submission of an
existing resident/shift reuses its job. No OpenAI connection is introduced.
