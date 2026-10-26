# CareLens UX contract

This captures the fall-history slice within the existing application; it does not
claim that every legacy screen has been migrated. Visual ownership is in DESIGN.md
and runtime tokens remain canonical in frontend/src/index.css.

## Business sources

| Domain | Source |
|---|---|
| Permission and role grants | app/modules/identity/permissions.py; migration 0032 |
| Resident/floor access and saved-result expiry | app/modules/resident_search/router.py; migration 0033 |
| Local deterministic fall lookup | app/modules/resident_search/service.py; evidence/falls.py |
| Privacy and intended-use boundary | governance/intelligence-pilot-data-policy.md |

## Canonical UI Map

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Date | Native input[type=date] in ResidentHistorySearch | API timestamp filters, inclusive UI end date | native, viewer local calendar | browser dates and boundary tests |
| Form | ResidentHistorySearch search form with shared Button | resident-search API | explicit submit with noValidate | browser validation and duplicate-submit checks |
| Scrollbar | frontend/src/index.css | runtime stylesheet | existing global baseline; document scrolling | narrow viewport inspection |

Table selection, select/listbox, toast, CRUD and overlays are not introduced by this
slice. Existing shared components remain the owners for sibling flows. New reusable
date behavior should be extracted if a second workflow needs this same contract.

## Search behavior

The Overview panel is visible for roles that mirror SEARCH_RESIDENT_HISTORY; the
server enforces current grants and RLS on every request. Missing or rejected access
leaves the native resident page available and shows an inline message. Do not add
new role grants as part of frontend work.

Show fall history submits explicitly, since each search saves a result and audits
access. Typing a date does not submit. Dates are optional; a selected end date includes
the full local day. Invalid ranges preserve values, associate an inline error and
focus the start field. Pending submit is disabled; changes and Clear cancel pending
requests and invalidate displayed results. A 20-second timeout provides a recovery
message. No automatic retry creates additional saved searches.

Search state is deliberately transient and sensitive: never persist it in URL params,
browser storage, telemetry or logs. Changing resident, staff identity or role resets
the panel. Unmount cancels requests; stale responses cannot replace current results.
Tabs retain their existing document scroll behavior.

## Results and source records

Show the deterministic count, coverage limits and at most 50 dated citations. Empty
results mean no matching records were found, not proof that no falls occurred. Render
clinical content as text. Open record fetches the current source through the saved
citation endpoint; expired, deleted or inaccessible sources show an inline message.
Reopening rechecks the source. A version change displays a refresh notice. Missing
values show Not recorded and booleans retain their source value.

## Accessibility and verification

Use native labels and buttons, noValidate forms, visible focus, status/alert regions,
keyboard-operable disclosures and natural document scrolling. Preserve full text
with wrapping and keep all actions available at 390px width. Reuse the existing
ResidentAIInsightsPanel as a sibling for cards, retry and cancellation behavior.
Verify Python adapter/service/RLS/HTTP tests, frontend production build, browser
success/empty/error/access/date/clear/stale-source paths, keyboard and narrow layout.
The browser test harness uses synthetic API responses and does not bypass production
authentication in shipped code.
