# Handover outbox publishing

Submission already commits a job and pending outbox row together. The dispatcher
now reserves that row, commits, publishes `intelligence.handover.generate`, then
records the outcome in a new tenant-scoped transaction. No broker call holds a
database row lock. No schema migration is required.

## Run locally

In intelligence-service/.env, set the trusted tenant allowlist as JSON:

```dotenv
INTELLIGENCE_DISPATCHER_TENANT_IDS=["YOUR_CARE_HOME_UUID"]
INTELLIGENCE_DISPATCHER_POLL_SECONDS=2
```

Replace the placeholder with actual UUIDs. The list must be nonempty; missing or
invalid configuration fails startup. Use the same database, broker and handover
queue as the API/worker. Do not put credentials or source records in task messages.

Run these alongside the API, from intelligence-service/:

```sh
.venv/bin/python -m intelligence.dispatcher
.venv/bin/celery -A intelligence.workers.celery_app:celery_app worker --loglevel=INFO
```

Each command is a separate long-running process/terminal. The dispatcher scans
each configured tenant, drains available work, and sleeps two seconds when idle.
SIGINT/SIGTERM stops the dispatcher after its bounded current iteration.

Alternatively, after configuring container-reachable database, Keycloak and
CareLens addresses:

```sh
docker compose --profile handover up --build api redis dispatcher worker
```

The profile connects dispatcher and worker to the Compose Redis on database 0.
Their queue still comes from INTELLIGENCE_HANDOVER_QUEUE. Do not mix a host worker
pointing at a different Redis database with the container dispatcher. Loopback
addresses inside containers do not address the host; use HTTPS endpoints for the
existing worker's non-loopback credential connections.

## Delivery behaviour

- A due pending row becomes publishing with a 60-second lease and a new token.
- Reservation honours both outbox available_at and job next_attempt_at.
- Successful Celery publication marks published, timestamps it, clears the lease
  and clears the error code. This means broker acceptance, not job completion.
- A publish error or 15-second publish timeout returns the row to pending with
  failure_code=publish_unconfirmed. Exponential backoff starts around five seconds,
  with jitter, capped at five minutes. Broker outages retry indefinitely; monitor
  the attempts count and queue age rather than silently discarding jobs.
- A dispatcher crash or failure to record broker success leaves a publishing row.
  Once its lease expires, any dispatcher for that tenant can reserve it again.
- Bookkeeping checks tenant, row, job, current token and unexpired lease. A stale
  dispatcher cannot overwrite a successor's outcome.
- The Celery message contains tenant_id and job_id only, with the outbox UUID as
  its stable task ID. Celery task IDs do NOT deduplicate execution. The worker's
  PostgreSQL job claim provides that protection.

Delivery is at least once: Redis may accept a message before the connection fails.
Retrying that uncertain outcome may produce a duplicate message. This is expected.
The synchronous broker call runs in a thread with transport timeouts; if cancellation
occurs, a send can still finish in that thread, so it must also be treated as uncertain.

This does not recover expired running handover jobs, retry generation failures, or
replace the need for broker durability. Those are separate from outbox delivery.
The API still needs live staff authentication before real pilot submission.

## Tests

Offline tests exercise dispatch sequencing, ambiguous outcomes, cancellation,
bookkeeping failure and actual Celery serialization via its in-memory transport.
PostgreSQL tests in tests/integration/persistence/test_outbox_delivery.py cover
state transitions, stale-token fencing, expired reservations, tenant isolation and
future-dated jobs. They require explicit local database opt-in. Existing independent
connection tests cover competing dispatchers with SKIP LOCKED.

No live Redis/PostgreSQL result is implied by offline tests. Monitor
outbox_publish_unconfirmed, outbox_lease_lost and outbox_dispatch_unavailable logs;
they intentionally omit raw broker/database errors that could contain credentials.
