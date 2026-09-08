# P0-01 — CareLens baseline review

Review date: 8 September 2026.

Status: source review complete; baseline recommendation recorded. Runtime verification is deferred to P0-02. Product acceptance of the baseline remains pending.

## Recommended baseline

Use the **current working tree**, including the five existing untracked application/migration files, as the candidate baseline to verify in P0-02. HEAD alone does not represent the application currently being developed. Preserve all current changes. Do not enable the experimental Celery event adapter as part of adopting this baseline.

This is a preservation and verification baseline, not a declaration that the application is production-ready. Resolve pilot-blocking defects in separately identified changes after baseline checks.

## Exact starting state

- Branch: `main`.
- HEAD: `d55a6d116486b0f47c0b221d9ef78aee4135b123` (`implymented celery worker successfully`).
- 128 changed tracked paths: 124 modified only in the working tree, one staged addition, and three staged additions with further unstaged changes.
- Five existing untracked application/migration files: `SyncStatusBadge.tsx`, `careEventQueue.ts`, `syncQueueStore.ts`, `migrations/README.md`, and migration `0029_care_event_idempotency_key.py`.
- The separate untracked intelligence implementation plan is planning work from this conversation.
- The index contains empty versions of `app/events/__init__.py`, `app/events/handler.py`, and `app/shared/celery_events.py`, plus an earlier version of `app/workers/tasks/events.py`. A commit of only the currently staged files would not capture the working implementation.

The accompanying [baseline manifest](baseline-manifest.json) records file hashes, Git status, HEAD and an index fingerprint. It excludes `docs/`, ignored files, databases and runtime state. It detects later changes but is **not a recoverable backup** or a record of applied database migrations. No secret configuration contents were copied into this report.

## Change groups and dependencies

| Group | Observed changes | Recommendation and dependencies |
|---|---|---|
| Shared import refactor | `app/__init__.py` adds a central re-export list; most module, test, synthetic-data and migration edits change imports to `from app import ...` | Preserve as one candidate group. Verify fresh process imports, test collection and migration execution in P0-02. Import order and eager loading now matter across modules. |
| Offline care recording | Three new frontend files, layout/header integration, care-entry save changes and token refresh | Keep UI, queue and backend idempotency changes together. Requires migration 0029. Address the integrity findings below before a pilot depends on offline data. |
| Backend idempotency | Care-event schema/model/service/repository changes and a unique nullable database key | Preserve with the offline feature. Verify concurrent retries and lost-response replay. Database migration application is unknown. |
| Experimental Celery events | New handler, event-bus adapter, task signature, named queues and explicit Kombu dependency/lock entry | Preserve as unfinished work. Active container still uses `InMemoryEventBus`; do not switch adapters yet. This is not durable external integration. |
| Documentation | Rewritten application README and new migration README | Preserve; claims about runtime behaviour still require P0-02 checks. |
| Generated frontend state | Modified tracked `tsconfig.app.tsbuildinfo` | Preserve existing state; record any changes caused by later builds separately. It is not independent feature work. |
| Intelligence planning | `docs/intelligence-implementation-plan.md` and this review | Keep separate from the application baseline in reviews and later commits. |

A Python AST comparison of changed tracked files, removing import statements, found remaining differences only in `app/__init__.py`, the three new event-plumbing files, `app/shared/celery.py`, and the four care-recording model/repository/schema/service files. This supports the classification of the remaining Python edits as import changes; it does not prove runtime equivalence because imports can have side effects.

## Confirmed source findings

These findings come from static inspection. Their runtime impact and regression tests belong in P0-02 or a separately scoped fix.

### B01 — readiness checks are not awaited

`app/main.py` calls asynchronous database and Redis functions without `await`. Coroutine objects are used for truth checks rather than executing the dependency probes. This defect is already present in HEAD; the current diff only changes imports in this file.

**Disposition:** planned P0-03 fix; do not rely on readiness before then.

### B02 — offline queue drops rejected records

`frontend/src/lib/careEventQueue.ts` removes queued entries on non-retryable responses such as 403 or 422. The queue/store has no failed-entry review state or explanation for the user. Entries previously described as saved offline can therefore disappear from the queue without being saved on the server.

**Disposition:** pilot blocker if offline recording is included. Preserve failed entries with a recoverable review state and test permission/validation failures.

### B03 — offline timestamps are not preserved by the current UI

`CareRecordEntryPage.tsx` builds payloads without `occurred_at`. The queue records a separate `queuedAt` but does not send it as the event time. The backend defaults missing occurrence time to database insertion time, so an entry synced later can be assigned to the wrong shift.

**Disposition:** data-quality blocker for handovers based on delayed offline records. Define occurrence versus recording time and preserve the intended occurrence time before the first request.

### B04 — queue ownership is not scoped to the original user

The queue uses one origin-wide localStorage key. Its item schema has no original actor or tenant field, and logout does not partition the queue. Subsequent syncing uses the currently authenticated session. A later user may submit an earlier user's queued payload under their own identity if authorised, or encounter denial followed by the removal described in B02. This is not evidence that server RLS can be bypassed.

**Disposition:** resolve queue ownership, retention and identity-switch behaviour before shared-device pilot use. Validate isolation and attribution.

### B05 — idempotency needs concurrent-retry and conflict semantics

The repository checks for an existing key before inserting. Concurrent requests can both pass that check and then race on the unique constraint; no `IntegrityError` handling was found in the application. The client also treats every replay-time HTTP 409 as already synced without validating the original payload/result. The constraint is global, while repository reads are tenant-scoped.

**Disposition:** define tenant-scoped key ownership and same-key/different-payload behaviour; validate concurrent retries and response-loss recovery. A unique constraint prevents duplicate rows but does not by itself guarantee a useful replay response.

### B06 — Celery integration is incomplete

- `build_container` instantiates `InMemoryEventBus`.
- `handle_care_event_recorded` forwards all task arguments, but no subscription to that handler was found.
- `CeleryEventBus.publish` forwards three arguments while the current task requires seven.
- The adapter stores subscribed handlers but does not invoke them, and silently ignores unmapped events. Switching to it would not preserve the current subscriber behaviour, including audit subscriptions.
- The new task only prints event identifiers; it does not process intelligence work.
- The code contains no transactional outbox for external delivery.

**Disposition:** retain these files as experimental. Specify durable integration in Phase 2; do not regard named queues or a task stub as completed external event delivery.

### B07 — migration and import changes require fresh-start verification

The old migration `0018_permissions_schema.py` now imports through the broad application barrel, and migration startup does likewise. The new care-event ORM column depends on untracked migration 0029. Database revision and fresh-install behaviour have not been checked.

**Disposition:** P0-02 should verify fresh migration execution against a disposable test database and distinguish migration prerequisites from application failures. Do not run migrations on a live database merely to complete this review.

### B08 — minor existing whitespace issue

`git diff --check` reports a new blank line at EOF in `app/workers/tasks/events.py`. This is recorded without editing it.

**Disposition:** non-blocking cleanup in the eventual event-plumbing change.

## Baseline acceptance recommendation

1. Preserve all current source changes as the candidate baseline; neither staged content nor HEAD alone is sufficient.
2. Keep the current in-memory event wiring until its replacement has explicit reliability and subscriber semantics.
3. Verify existing work in P0-02 before making broader architectural changes.
4. Fix readiness under P0-03. Track B02–B05 as explicit follow-up work before any pilot that relies on offline care records.
5. Keep the future intelligence runtime independent of the application barrel imports and ORM.

No application changes were made, and nothing was staged, committed, stashed, reset or migrated during this review.

## Isolation approach for subsequent implementation

The review and hash manifest provide a comparison point without changing the checkout. They do not physically isolate future edits.

Before implementation changes begin, create a coherent baseline checkpoint after review, then use a dedicated `codex/` branch/worktree based on that checkpoint. A worktree created from current HEAD alone would omit the uncommitted implementation. If checkpointing is deferred, use small file/hunk-scoped changes against this manifest and explicitly distinguish pre-existing changes; that is weaker isolation and should be temporary.

Do not create a new intelligence repository in an arbitrary location during P0-01. Its location and access arrangements belong to Phase 1 setup.

## Next item: P0-02

Run backend and frontend baseline checks, record each result and prerequisite, and reproduce the relevant source findings with focused checks where practical. Leave broad refactoring and unrelated remediation outside that verification task.

P0-01's review deliverable is complete. The roadmap checkbox remains open because the recommended baseline has not yet been explicitly accepted and physical implementation isolation has not been established.
