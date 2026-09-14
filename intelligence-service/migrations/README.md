# Intelligence persistence migrations

This is an independent Alembic migration history. It does not use CareLens's
migration directory, application settings, or `DATABASE_URL`.

## Prerequisites

Create the `intelligence` database, `intelligence_migrator` owner and
`intelligence_app` runtime role using the database setup discussed separately.
The migration expects `intelligence_app` to exist; it does not create cluster roles
or passwords. The migrator needs schema creation/ownership privileges.

From `intelligence-service/`, install the PostgreSQL driver if not installed:

```sh
uv add 'psycopg[binary]>=3.2,<4'
```

Alembic and SQLAlchemy are already declared in this project's dependencies.
Keep migration credentials separate from the API/worker credentials:

```dotenv
INTELLIGENCE_MIGRATION_DATABASE_URL=postgresql+psycopg://intelligence_migrator:URL_ENCODED_PASSWORD@127.0.0.1:5432/intelligence
```

The migration environment loads this variable from the process environment or
`intelligence-service/.env`, without requiring a demo API token. Environment values
win. Use the actual host port. It deliberately does not fall back to CareLens's
connection URL or the runtime account. Check that the configured database is the
intelligence database before applying.

## Preview and apply

From `intelligence-service/`:

```sh
uv run alembic history
uv run alembic upgrade head --sql > /tmp/intelligence-upgrade.sql
uv run alembic upgrade head
uv run alembic current
```

The SQL preview needs no database connection or password. Online migration needs
psycopg and the configured migration URL. No migration has been applied by the
assistant; only offline SQL generation and static checks were performed.

For a disposable database only, rollback/reapply verification can use:

```sh
uv run alembic downgrade base
uv run alembic upgrade head
```

Downgrade drops all four tables and their data. Do not run it against retained jobs
or handovers. Existing manually created tables are not adopted or overwritten;
reconcile them before applying rather than adding `IF NOT EXISTS` to mask drift.

## Revision 0001_handover

| Table | Guarantees / intended use |
|---|---|
| `handover_jobs` | Unique tenant/idempotency key and tenant/resident/shift/generation; manual actor required; generation links stay within resident/shift; lease fields and checked states |
| `dispatch_outbox` | Job-bound dispatch rows, unique dispatch number, bounded identifiers instead of clinical task payloads; publication lease/state fields |
| `evidence_manifests` | Immutable snapshots containing source references/versions, warnings, retrieval time and optional real source cutoff; job/resident/tenant linkage |
| `handover_draft_versions` | One AI original per job, ordered-version uniqueness, same-job predecessor and manifest links, immutable content and generation provenance |

Use `generation_number=1` for the first logical resident/shift job. Intentional
regeneration uses a new job/idempotency key and a higher generation number linked
to `previous_job_id`. Allocate that number transactionally and handle uniqueness
conflicts. Repeated identical submissions return the existing job; an idempotency
key reused with a different request must be rejected by application code.

A retry of the same job may produce a new evidence manifest using its attempt
lease token. It must not create another AI original. One transaction should save
the accepted original and transition the job to `draft_ready`.

Sources/warnings/sections are JSON arrays. The database checks array shape, not
full nested clinical schemas. Validate them using versioned application contracts.
Use non-sensitive `failure_code` values; do not store exception dumps or tokens.

## Transaction-scoped tenant access

Every table enables **FORCE RLS** with both read and write tenant checks using
`intelligence.tenant_id`. Missing/empty context matches no tenant. Malformed UUID
context fails rather than opening access. Always set context inside the same
transaction that performs the queries:

```python
with session.begin():
    session.execute(
        text("SELECT set_config('intelligence.tenant_id', :tenant_id, true)"),
        {"tenant_id": str(authorised_tenant_id)},
    )
    # Tenant-scoped reads/writes here.
```

The tenant must come from verified server-side authority. RLS here is tenant
isolation, not complete resident/floor or role authorisation. Application checks
are still required for eligibility, current staff access and nurse-in-charge
sign-off. A runtime DB credential can set this context: do not expose it to users.
The migration owner and PostgreSQL administrators are privileged operational
accounts, not API/worker credentials.

`intelligence_app` can SELECT/INSERT all four tables, UPDATE jobs/outbox, and
cannot UPDATE immutable evidence/drafts or DELETE any of these records. UPDATE
triggers additionally reject changes to evidence/drafts even by the owner under
ordinary operation. Audit/retention deletion needs a separately designed
privileged process with hold checks; this migration does not implement purge.
Default grants to `alembic_version` are removed from the runtime role. Keep runtime
credentials out of the migration process and vice versa.

## Worker and outbox repository work still required

Lease columns support atomic claiming but do not claim work automatically. In the
repository implement conditional UPDATE/RETURNING or SELECT FOR UPDATE followed
by an update in the same transaction. Set a fresh `lease_token`, expiry and attempt
counter on each claim. Heartbeats and completion must match the current token.

Before saving output, lock and verify the job is still running with the matching,
unexpired lease, insert the manifest/draft and transition state within that same
transaction. Clear lease fields and set `completed_at` for terminal states. An old
worker must never save after a new worker has acquired the lease.

Create job + initial outbox in one transaction. Publish identifiers only. If a
publisher crashes after sending but before marking `published`, replay is expected;
the task must deduplicate using durable job state. A published row is not proof of
worker completion. Reconciliation can add a new dispatch number for a recoverable
job after checking its lease and attempt policy.

Constraints validate state values and field consistency, not the complete legal
transition graph, maximum attempts, lease ownership or version-number succession.
Those checks must be implemented and tested in repositories. No endpoint, Celery
task, dispatcher or operational recovery behaviour is created by this migration.

## Review and finalisation boundary

Generation status is independent of clinical review. There is deliberately no
editable `finalised` flag on an AI draft. CareLens owns authoritative review state,
nurse-in-charge sign-off and signed handovers. Add authenticated linking/integration
when implementing that feature; do not mistake `draft_ready` for approval.

Retain the AI original linked to a signed handover under the official record
policy. The 30-day abandoned-draft rule must not delete retained signed evidence.

## Database verification to run before wiring the worker

Use a disposable PostgreSQL database with the real non-superuser runtime role:

1. Upgrade → downgrade → upgrade; inspect all constraints, indexes and policies.
2. Insert job + outbox in one transaction, force rollback and verify neither exists.
3. Concurrently submit the same shift/generation and check only one job is accepted.
4. Set tenant A context; verify tenant B reads return nothing and cross-tenant writes fail.
5. Verify cross-resident manifests and cross-job draft predecessor links fail.
6. Verify duplicate originals and UPDATE/DELETE attempts fail for the runtime role.
7. Once repository code exists, test expired-lease takeover, stale completion,
   idempotent retry and concurrent version allocation against PostgreSQL.

No ORM metadata has been added in this scope. New revisions should be written
explicitly (`alembic revision -m ...`); autogeneration requires defining and wiring
SQLAlchemy metadata in a later persistence implementation step.
