# CareLens — Alembic Migrations

This is your tested database schema (`carelens-schema.sql`), split into 11 Alembic
migrations — one per logical table group, matching the order in the Week 1 guide.
Every migration in this folder has been run against a real PostgreSQL 16 instance:
`alembic upgrade head` succeeds, `alembic downgrade base` cleanly removes everything
(tables, types, extensions), and re-running `upgrade head` afterwards works again.

## Why Alembic here, and how it fits your project

Alembic doesn't replace the SQL you already have — it version-controls the *order*
in which it's applied, and gives you a safe way to move a database forward or
backward one step at a time as your schema evolves. Each migration file has two
functions: `upgrade()` (apply this change) and `downgrade()` (undo it). Alembic
tracks which migrations have run in a small table it creates itself
(`alembic_version`), so it always knows the current state of any given database.

Two ways to write a migration's `upgrade()`:
1. **Raw SQL via `op.execute(...)`** — what this project uses throughout, because
   your schema was designed and tested as SQL directly (RLS policies, `DO` blocks,
   generated columns — things that don't map cleanly onto Alembic's Python
   operations helpers like `op.create_table`).
2. **Alembic's Python operations** (`op.create_table`, `op.add_column`, etc.) —
   more idiomatic for simple column-level changes later, and what `--autogenerate`
   produces if you introduce SQLAlchemy ORM models. You'll likely use this style
   for smaller Phase 2+ changes; the raw-SQL style here is right for a large
   initial schema with RLS and triggers.

## Folder layout

```
carelens-alembic/
├── alembic.ini              # Alembic config; points at migrations/
└── migrations/
    ├── env.py               # reads DATABASE_URL from the environment
    ├── script.py.mako       # template used when you generate new migrations
    └── versions/
        ├── 0001_extensions_enums_helpers.py
        ├── 0002_tenancy_and_identity.py
        ├── 0003_residents_core.py
        ├── 0004_person_centred_and_clinical_foundation.py
        ├── 0005_care_planning.py
        ├── 0006_daily_care_domains.py
        ├── 0007_medications.py
        ├── 0008_activities_visits_incidents.py
        ├── 0009_ai_outputs_and_audit_log.py
        ├── 0010_row_level_security.py
        └── 0011_updated_at_triggers_and_indexes.py
```

Each migration's `down_revision` chains to the previous one, so Alembic always
knows the exact order: 0001 → 0002 → ... → 0011.

## How to add this to your own repo

1. Copy the `carelens-alembic/` folder into your project root — or copy just
   `alembic.ini` and `migrations/` if your repo structure differs, and adjust
   `script_location` in `alembic.ini` if you move `migrations/` elsewhere.
2. Install dependencies (already in your stack):
   ```bash
   pip install alembic sqlalchemy psycopg2-binary --break-system-packages
   ```
3. Set `DATABASE_URL` as an environment variable — never hardcode it:
   ```bash
   export DATABASE_URL="postgresql+psycopg2://carelens_owner:yourpassword@localhost:5432/carelens"
   ```
   Use your **owner/migration role** here (see the Week 1 guide) — not the
   restricted app role, since migrations need DDL rights.
4. From the folder containing `alembic.ini`, run:
   ```bash
   alembic upgrade head
   ```
   This applies all 11 migrations in order against whatever database
   `DATABASE_URL` points to.

## Common commands you'll use going forward

```bash
alembic current                 # what revision is this database on?
alembic history                 # show the full migration chain
alembic upgrade head             # apply all pending migrations
alembic upgrade +1                # apply just the next one
alembic downgrade -1              # undo the most recent one
alembic downgrade base            # undo everything (used in tests/CI)
alembic revision -m "add x"       # create a new empty migration file to fill in
```

## Adding a new migration later (Phase 2 onward)

```bash
alembic revision -m "add change_detection_flags table"
```
This creates a new file in `migrations/versions/` with `down_revision` already
set to whatever your current head is. Fill in `upgrade()` and `downgrade()`,
then `alembic upgrade head` to apply it. Keep doing this one logical change at
a time — resist bundling unrelated schema changes into one migration, for the
same reason the initial schema was split into 11 rather than shipped as one.

## Important: the app role and RLS

Migration `0010_row_level_security.py` enables and forces RLS on every tenant
table. Your **application** must connect using the restricted `app_user` role
(see Week 1 guide, Step 3) — not the owner role used to run migrations —
or RLS won't apply the way you expect while you're testing manually. If you
haven't created that role yet, do it once per environment (a small bootstrap
script or an early migration), for example:

```sql
CREATE ROLE app_user LOGIN PASSWORD '...';
GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO app_user;
REVOKE UPDATE, DELETE ON audit_events FROM app_user;
GRANT SELECT, INSERT ON audit_events TO app_user;
```

## Verifying it works in your own environment

The same checks from the Week 1 guide apply here directly:

```bash
alembic upgrade head      # should succeed with no errors
alembic downgrade base    # should succeed and leave only alembic_version behind
alembic upgrade head      # should succeed again — proves the round-trip is clean
```

If any step fails, the error will point at the specific migration file and SQL
statement — fix it there rather than editing the database by hand.
