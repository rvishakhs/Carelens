# Independent intelligence service

A runnable **synthetic-only skeleton**, separately packaged from CareLens. Two registered agent paths exercise request → scoped evidence → deterministic metrics → gateway → fake provider → validated cited result. The history path is a demo of fluid totals, not natural-language search. The handover path returns an unreviewed draft, not a complete clinical handover.

Start with [architecture and stack](docs/architecture.md), then [delivery plan](docs/delivery-plan.md) and [adding an agent](docs/adding-agents.md).

## Run locally

Requires Python 3.12 and uv. Run from this directory:

```sh
uv sync --frozen
cp .env.example .env
```

For this workspace, a local `.env` and independent `.venv` have already been created; preserve them rather than copying over `.env`. On a fresh checkout, generate a token with `python -c "import secrets; print(secrets.token_urlsafe(32))"` and replace `INTELLIGENCE_DEMO_TOKEN` in `.env`. The example token is deliberately rejected. Do not reuse CareLens credentials.

```sh
uv run --frozen uvicorn intelligence.api.app:create_app --factory --host 127.0.0.1 --port 8100 --no-access-log
```

Open `http://127.0.0.1:8100/docs`, choose **Authorize** and enter the demo token. Use the POST `/v1/runs` example below. `GET /readyz` explicitly reports synthetic mode and no durable/live integrations.

```json
{
  "agent_id": "resident_history",
  "resident_id": "30000000-0000-0000-0000-000000000001",
  "period": {
    "start": "2026-09-08T00:00:00+01:00",
    "end": "2026-09-09T00:00:00+01:00"
  },
  "question": "Show recorded fluid totals"
}
```

Expected: 450 ml consumed, 630 ml offered, and three synthetic source references. Change `agent_id` to `handover_draft` to receive `state: draft`. The period is deliberately fixed to the fixture date. Empty periods return “no records”, not zero intake. Question text is accepted to establish the request contract but **is not interpreted, persisted or sent to the fake provider**. Only use synthetic inputs.

With the API running, exercise both paths without copying the token into a command:

```sh
uv run --frozen python scripts/demo.py
```

The versioned schema is also available in [the OpenAPI snapshot](docs/openapi.json).

Alternatively, after configuring `.env`:

```sh
docker compose up --build
```

The service binds host port 8100 on loopback, independently of CareLens on port 8000. Compose runs only the API. Supply a reachable independent PostgreSQL URL; localhost inside the container is not the host database. Do not run multiple API processes against the in-memory result adapter: results would differ per process.

## Test

```sh
uv run --frozen pytest --confcutdir=tests
uv run --frozen ruff check src tests
uv run --frozen ruff format --check src tests
uv run --frozen mypy src
```

`--confcutdir=tests` prevents a parent repository's pytest fixtures from leaking into this project. The package has no `app` imports or shared runtime configuration. See [verification](docs/verification.md) for what was actually checked.

## What exists

- Independent Python package, dependency lock, container recipe and local Compose entry point.
- Versioned request/result/evidence contracts with strict validation.
- Two registered bounded agents, an evidence-reader port and a synthetic connector.
- Structured gateway with request-local source aliases, deterministic totals and response validation.
- Required local token with fixed **server-owned synthetic** tenant/resident permissions.
- Bounded in-memory result storage with access rechecks and lazy expiry (15 minutes, 100 results).
- Authenticated run/catalogue/result routes, liveness and honestly scoped readiness.
- Tests and extension/architecture/delivery documents.

## What does not exist yet

Live CareLens connector/delegated OIDC, complete persistent submission API, Celery dispatch/workers, outbox delivery, full 14-source mapping, hybrid search, free-text pseudonymisation, real models, clinical evaluations, signed review/amendment APIs, scheduled deletion and cloud deployment. `mode=production` and real providers fail configuration validation. The fake provider has no network calls.

The current alias resolution restores internal source references and attaches the authorised resident ID to the response; it does **not** demonstrate name redaction/re-identification of arbitrary clinical text. That gateway upgrade is a separate milestone with leakage tests.

## Separate repository

This directory is a self-contained project placed here because the current writable workspace is CareLens. It is **not yet a separate Git repository**. It can be copied/moved into an independent checkout: all build/runtime imports, tests and dependency files are local. Copy the approved CareLens governance/evaluation documents as a reviewed snapshot when making that move; do not copy real data, `.env`, `.venv`, caches or application credentials. There is no need to copy the CareLens `app/` directory.

Technical developer/reviewer: project owner (you). Care reviewer: Glenrose. Finalisation policy: only the designated nurse in charge; implementation deferred to the CareLens review integration milestone.

## Persistence layout and local checks

- `src/intelligence/`: installed application package.
- `src/intelligence/persistence/`: engine/session lifecycle and ORM models.
- `src/intelligence/handover/`: handover contracts and submission insertion primitive.
- `migrations/versions/`: active schema history, including tenant policies and permissions.
- `migration_backups/`: inactive migration text retained for reference only.
- `scripts/`: explicitly invoked local checks and demos.
- `tests/`: automated tests, with PostgreSQL checks opt-in.

Runtime/API and tenant checks read `INTELLIGENCE_DATABASE_URL` using the
`intelligence_app` role. Alembic reads only `INTELLIGENCE_MIGRATION_DATABASE_URL`,
using `intelligence_migrator`; it does not require the API demo token.
Store credentials in `.env`, never in tracked files.

```sh
uv run python scripts/check_tenant_access.py
# Equivalent opt-in pytest entry point:
INTELLIGENCE_RUN_DB_TESTS=1 uv run pytest --confcutdir=tests tests/test_tenant_access.py -s
```

The check uses synthetic UUIDs and rolls back its transaction. It checks tenant
visibility, denied inserts and immutable request mappings as the runtime role.
The regular synthetic API tests stub database startup/readiness and do not prove
PostgreSQL connectivity; use the integration check for that.

Psycopg includes its binary driver so local checks do not depend on a system
libpq installation. `requirements.lock` is exported from `uv.lock` for the
existing Dockerfile; refresh it after dependency changes with:

```sh
uv export --frozen --no-dev --no-emit-project -o requirements.lock
```

Container execution has not been verified.

Persistence tables/RLS exist, but the submission insertion primitive is not a
complete endpoint: request replay, concurrent duplicate handling, shift/eligibility
validation and worker dispatch still need implementation. Existing `/v1/runs`
results remain in memory.
