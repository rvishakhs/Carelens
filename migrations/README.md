# CareLens — Alembic Migrations

The database schema, applied as a chain of Alembic migrations under
`migrations/versions/`, one per logical change. Every migration here has been run
against a real PostgreSQL 16 instance: `alembic upgrade head` succeeds, and each
migration ships a working `downgrade()`.

## Why Alembic here, and how it fits this project

Alembic doesn't replace the SQL — it version-controls the *order* in which it's
applied, and gives a safe way to move a database forward or backward one step at a
time as the schema evolves. Each migration file has two functions: `upgrade()`
(apply this change) and `downgrade()` (undo it). Alembic tracks which migrations have
run in a small table it creates itself (`alembic_version`).

Almost every migration here writes raw SQL via `op.execute(...)` rather than
Alembic's Python operations helpers (`op.create_table`, etc.) — the schema leans on
RLS policies, triggers, `DO` blocks, and generated columns that don't map cleanly
onto those helpers.

## Folder layout

```
migrations/
├── env.py               # reads DATABASE_URL from the environment
├── script.py.mako       # template used when generating new migrations
└── versions/
    ├── 0001_extensions_enums_helpers.py
    ├── 0002_tenancy_and_identity.py
    ├── ...
    └── 0029_care_event_idempotency_key.py   # current head
```

Each migration's `down_revision` chains to the previous one, so Alembic always knows
the exact order. See the top-level README's "Data model" section for what each
numbered range actually built.

## Common commands

```bash
alembic current                  # what revision is this database on?
alembic history                  # show the full migration chain
alembic upgrade head             # apply all pending migrations
alembic upgrade +1               # apply just the next one
alembic downgrade -1             # undo the most recent one
alembic downgrade base           # undo everything (used in tests/CI)
alembic revision -m "add x"      # create a new empty migration file to fill in
```

## Adding a new migration

```bash
alembic revision -m "add change_detection_flags table"
```

This creates a new file with `down_revision` already set to the current head. Fill
in `upgrade()` and `downgrade()`, then `alembic upgrade head` to apply it. Keep each
migration to one logical change — resist bundling unrelated schema changes together.

## The app role and RLS

Migration `0010_row_level_security.py` enables and forces RLS on every tenant table.
The **application** connects using the restricted `app_user` role — not the
owner/migration role — or RLS won't apply the way you'd expect while testing
manually. Bootstrap it once per environment:

```sql
CREATE ROLE app_user LOGIN PASSWORD '...';
GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO app_user;
REVOKE UPDATE, DELETE ON audit_events FROM app_user;
GRANT SELECT, INSERT ON audit_events TO app_user;
```

## Verifying a clean round-trip

```bash
alembic upgrade head      # should succeed with no errors
alembic downgrade base    # should succeed and leave only alembic_version behind
alembic upgrade head      # should succeed again -- proves the round-trip is clean
```

If any step fails, the error points at the specific migration file and SQL
statement — fix it there rather than editing the database by hand.
