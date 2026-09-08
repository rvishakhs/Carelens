# CareLens

CareLens is a care-home management platform for residential/nursing care providers:
resident records, template-driven care recording, care plans, medications, AI-assisted
daily summaries, and staff/RBAC administration — built as a modular monolith backend
with a separate React SPA frontend, on top of a multi-tenant, row-level-secured
Postgres database.

---

## 1. System architecture

### 1.1 High-level shape

```
┌─────────────────────┐        ┌──────────────────────────────────────────┐
│   React SPA (Vite)   │  HTTP  │              FastAPI backend              │
│   frontend/src        │ ─────▶ │         (modular monolith, app/)          │
│                      │        │                                          │
│  Keycloak login ─────┼───────▶│  Keycloak (OIDC) — auth, roles           │
└─────────────────────┘        │                                          │
                                │  Postgres 16 — one schema, RLS-isolated  │
                                │  per care_home_id (+ floor scoping)      │
                                │                                          │
                                │  Redis — Celery broker/result backend    │
                                │  Celery workers + APScheduler — async    │
                                │  jobs, daily AI summaries, retention     │
                                └──────────────────────────────────────────┘
```

`docker-compose.yml` runs the full stack for local dev: `postgres`, `pgbouncer`
(transaction-mode pooling in front of Postgres), `redis`, `mailpit` (dev SMTP),
`keycloak` (realm auto-imported from `keycloak/realm-export.json`), `app`
(FastAPI), and `worker` (Celery). Backend and frontend run as separate processes —
there's no server-side rendering or shared build step between them.

### 1.2 Backend: modular monolith, ports & adapters

Every feature area lives under `app/modules/<name>/`, and every module has the same
shape:

| File | Purpose |
|---|---|
| `models.py` | SQLAlchemy ORM tables. Only this module (and Alembic) imports it. |
| `schemas.py` | Pydantic request/response DTOs, plus cross-module read shapes. |
| `ports.py` | Abstract interfaces — **Reader ports** other modules may depend on (e.g. `ResidentReader`), and **external ports** this module depends on (e.g. `TokenVerifier`). |
| `repository.py` | DB access. Implements the module's own reader port directly. |
| `service.py` | Business logic / use-cases. Orchestrates the repository, other modules' ports, and the event bus. Never touches FastAPI. |
| `dependencies.py` | FastAPI dependency-provider functions (`get_x_reader`, `get_x_service`) — the file other modules actually import from. |
| `router.py` | FastAPI routes. Thin: `permissions.require(...)`, call the service, return the schema. |
| `events.py` | `DomainEvent` subclasses this module publishes. |
| `module.py` | Exactly one function, `register(app, container)` — the only thing `app/main.py` calls per module. |
| `adapters/` (where present) | Concrete implementations of this module's *external* ports. |

**The rule this enforces**: module A may import module B's `ports.py`,
`dependencies.py`, `schemas.py`, and `events.py` — never B's `repository.py` or
`models.py`. This is what lets `ENABLED_MODULES` in `.env` drop a module without
touching anyone else's code, and is why `medications` (a Phase-2 feature) could sit
disabled for a while and then get turned on with a one-line config change.

Everything imports its cross-module dependencies from a single barrel file,
`app/__init__.py` — a dependency-ordered set of re-exports built from the actual
import graph (no manual sequencing). A handful of genuinely ambiguous names (every
module's own `router.py` router, every module's own `register()`) are deliberately
excluded from the barrel and imported directly from their owning submodule instead,
since a flat namespace can't hold eleven different things all called `router`.

**Modules currently enabled** (`ENABLED_MODULES` in `.env`): `identity`, `residents`,
`floors`, `observations`, `care_recording`, `audit`, `ai_gateway`, `summaries`,
`ai_insights`, `handover`, `medications`.

### 1.3 Multi-tenancy & row-level security

Every tenant table carries `care_home_id` (and, for floor-scoped data, `floor_id`).
Postgres RLS is **enabled and forced** on every tenant table (migration `0010`); a
DB session that never sets tenant context sees zero rows — there is no other way to
read tenant data. The pattern used everywhere:

```python
async def get_resident_repository(current_user: CurrentUser = Depends(get_current_user)):
    async with rls_session(current_user.care_home_id, current_user.id, current_user.floor_ids) as session:
        yield ResidentRepository(session)
```

`rls_session()` (`app/shared/database.py`) opens a session and runs `SET LOCAL
app.care_home_id = ...` / `app.user_id = ...` / `app.floor_ids = ...` inside the
transaction before yielding it. `system_session()` (no context set) exists only for
rare cross-tenant system operations, deliberately named to stand out in a diff.

### 1.4 Auth & RBAC

Login is Keycloak (OIDC) end to end — the frontend never handles a password.
`app/modules/identity/permissions.py` holds the full role → permission matrix:

```python
class Role(str, enum.Enum):
    CARER = "carer"; NURSE = "nurse"; MANAGER = "manager"; FAMILY = "family"
    EMERGENCY = "emergency"; ADMIN = "admin"; HEADOFFICE = "headoffice"; SYSTEM_ADMIN = "system_admin"
```

A route is protected with one line —
`current_user: CurrentUser = Depends(require(Permission.RECORD_CARE_EVENT))` — which
first verifies the JWT and just-in-time-provisions a local `users` row keyed off the
Keycloak subject (so RLS/audit always have a stable `user_id`), then checks the
permission registry (DB-backed, editable without a deploy) and 403s on a miss.

### 1.5 Domain events & audit trail

`app/shared/events.py` defines `DomainEvent` + `EventBus`; `InMemoryEventBus` is the
adapter actually wired into the container today (`app/container.py`), so publish/
subscribe is in-process and synchronous-within-the-request. A `CeleryEventBus`
adapter and a matching Celery task (`app/shared/celery_events.py`,
`app/workers/tasks/events.py`, `app/events/handler.py`) already exist for routing
specific events to an out-of-process worker instead, but aren't switched on in
`build_container` yet — the port/adapter seam is there, the wiring isn't.

Publishers never import the audit module directly. Instead, `app/modules/audit/
module.py` imports every other module's `events.py` and subscribes a handler per
event type at startup — each handler opens its own `rls_session()` and writes one
immutable `audit_events` row (that table has no `updated_at`, and a DB trigger
enforces no `UPDATE`/`DELETE`, ever). This is what makes every read *and* write
auditable without every module needing to know audit exists.

### 1.6 AI gateway — pseudonymise → LLM → re-identify

`app/modules/ai_gateway/` sits between every LLM call and the outside world:

1. `pseudonymise()` swaps the resident's real identity for a stable, per-resident
   HMAC token before anything reaches a prompt — prompts are built from templates
   that only ever reference `{{RESIDENT}}`, never a real name to begin with — and
   regex-strips incidental PII (NHS numbers, UK phone numbers, date-like strings)
   from free text.
2. The (pseudonymised) prompt goes to whichever `LLMProvider` adapter is selected via
   `LLM_PROVIDER` in `.env`: `fake` (deterministic canned response, dev default),
   `local` (an Ollama-style endpoint), or `real` (stubbed — see below).
3. `re_identify()` swaps the token back for the real display name in the response.

`RealLLMProvider.complete()` deliberately raises `NotImplementedError` — there's no
NER pass yet to catch a name spelled out *inside* a free-text note (tracked as
hazard-log entry H-003, `governance/hazard-log.md`), so nothing routes real resident
data through a real external LLM provider until that gap closes.

### 1.7 Background work

`app/workers/scheduler.py` runs APScheduler cron jobs (daily AI summary generation,
a nightly retention sweep) as a separate process; `worker` in `docker-compose.yml`
runs a Celery worker consuming `app/workers/tasks/` — currently just the task queue
infrastructure plus the not-yet-wired `care_event_recorded` task from section 1.5,
ready for more to move off the request path as they're switched on.

### 1.8 Frontend

React 18 + TypeScript + Vite, Tailwind v4, `react-router-dom` for routing, `zustand`
for the small amount of global client state (`authStore`, `staffStore`, `uiStore`,
`syncQueueStore`), and hand-rolled `axios` fetch wrappers (`utils/helper.ts`) — no
React Query/SWR, no Redux. `keycloak-js` handles login; `ProtectedRoute` blocks
rendering until `/identity/me` resolves. UI primitives (`Card`, `Button`, `Modal`,
`Pill`, `Tile`, `Tabs`, `Avatar`) live in `components/ui/` and are shared across
every page; layout chrome (`Sidebar`, `PageHeader`, `AppLayout`) lives in
`components/layout/`.

---

## 2. What's built so far

### 2.1 Template-driven care recording (the core feature)

The largest single piece of work: a metadata-driven engine (migration `0014`) that
lets staff record any kind of care entry — nutrition, personal care, toileting,
mobility, medical, behaviour, sleeping, safety checks, activities, communication,
processes — through one consistent tap-through flow, instead of a bespoke form per
care type.

**Schema**: `care_categories` → `care_templates` → `care_template_sections` (single-
or multi-select, `allow_multiple`) → `care_template_options`, plus
`care_template_measurements` (numeric/text/boolean, with units and bounds) per
template. A recorded entry is a `care_event` with child `care_event_options` /
`care_event_measurements` rows.

**Currently seeded** (migrations `0015`, `0021`–`0028`): **11 categories, 243
templates, 308 sections, 1,450 options** — covering Nutrition & Hydration (meal-size
and drink-quantity-offered fields, not just "amount eaten"), Personal Care (bath
type, denture care sub-actions, oral hygiene per NHS charting practice, hearing-aid
actions), Personal Safety & Environment (bed-rail entrapment checks, hoist sling
condition, footwear falls-prevention), Toileting (continence charting, Bristol stool
type + colour), Mobility (equipment used, full post-fall incident protocol —
location/witnessed/injury/actions-taken), Emotional Support & Behaviour
(trigger → intervention → response, modelled on BPSD charting guidance), Medical,
Communication, Sleeping, Processes, Activities.

**Recording flow** (`frontend/src/pages/CareRecordEntryPage.tsx`): every category
expands inline with a single global search box; templates render as square tiles
(icons from a custom `@carelens/icons` package, matched by template name); tapping
one or more tiles and hitting Continue shows every selected entry's detail form in
one page — status, its sections as tiles (radio for single-select, toggled
independently for multi-select), its measurements, and a **live-generated care
note** that composes itself from whatever's selected (e.g. *"Breakfast. Food: Cereal,
Porridge. Amount Eaten: Most."*) with a small pencil icon to append free text, rather
than a blank notes box. A required "time spent" field feeds resident-level
staffing/resource-need reporting. Every save also auto-generates the same narrative
`summary` text server-side (`_build_summary`, `app/modules/care_recording/
service.py`) — the intended input for a future embedding/vector pipeline.

**Care Records history** (`ResidentDetailPage.tsx`'s Care Records tab): past entries
render as the same square tiles, colour-coded green/amber/red for
completed/declined/refused, with the same icons; tapping one shows category, status,
performer, and the generated summary.

### 2.2 Offline-durable recording + idempotent writes

`POST /care-recording/events` accepts a client-generated `idempotency_key`
(migration `0029`, mirroring the existing pattern in `observations`); a duplicate
key raises `409 Conflict` instead of inserting a second row. The frontend
(`lib/careEventQueue.ts`) uses this to make saving resilient to short outages: a
failed save (network error, 5xx, or an expired-session 401) is queued in
`localStorage` with its key already attached, rather than lost; a background sync
(on load, on the browser's `online` event, and every 20s while anything's pending)
drains the queue, treating both success and 409 as "done." A header badge
(`SyncStatusBadge`) shows the pending count with a manual retry. `lib/api.ts`'s
request interceptor also now calls `keycloak.updateToken(30)` before every request,
fixing the token-expiry 401s that made this durability layer necessary in the first
place.

### 2.3 Residents

List page (`ResidentsPage.tsx`) as a blended, sortable list (not a boxed table) with
real resident photos where set; detail page (`ResidentDetailPage.tsx`) with a
profile header (photo, room/age/gender, allergy and DNACPR flags), an Overview tab
(at-a-glance risk indicators, vitals, recent activity, care plan goals preview,
diagnoses/allergies/contacts/advance directives), plus Care Records, Care Plan, and
Activity tabs.

### 2.4 Identity, staffing, and the rest of the module surface

Staff administration (create/deactivate/reset-password via the Keycloak admin
client), floors and floor-scoped access grants, care plans with structured goals,
observations (vitals/notes with plausibility checks), medications (schedule +
event recording, currently enabled), AI insights (alerts, predictions, generated
reports/summaries with feedback), and a handover view that ranks residents by
recency-weighted risk signals across observations/summaries.

### 2.5 Data model

**29 Alembic migrations** (`migrations/versions/`, see `migrations/README.md`):
extensions/enums → tenancy & identity → residents core → clinical foundation → care
planning → daily care domains → medications → activities/incidents → AI outputs &
audit → row-level security → triggers/indexes → care-home policy → floors →
**the care template/event engine + its seed library** → AI knowledge layer → delete
policies → permissions schema → identity bootstrap → structured care plan goals &
appointments → duration/summary/idempotency additions and category-content
expansions on the care recording engine.

**Synthetic data**: `synthdata generate --residents 40 --days 90 --seed 42` seeds 40
residents with persona-driven trajectories (stable / gradual decline / post-fall
recovery / UTI episode) and realistic daily observations — the current dev database
has 40 residents' worth of this seeded.

---

## 3. Running it locally

```bash
# --- backend ---
cp .env.example .env               # fill in real values
docker compose up -d postgres pgbouncer redis keycloak   # infra only
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload      # http://localhost:8000, docs at /docs

# --- background jobs (separate processes, optional for basic use) ---
uv run python -m app.workers.scheduler
uv run celery -A app.shared.celery:celery_app worker

# --- frontend ---
cd frontend
npm install
npm run dev                         # http://localhost:5173

# --- synthetic data (after migrations) ---
uv run synthdata generate --residents 40 --days 90 --seed 42
```

## 4. Testing

```bash
uv run pytest -q                    # unit + rbac + integration (needs alembic on PATH
                                     # for the testcontainers fixture, or run with
                                     # PATH=".venv/bin:$PATH" as a shortcut)

cd frontend && npm run build        # TypeScript typecheck + production build
```

## 5. Where to look next

- **`walkthrough.md`** — a detailed companion doc to the initial backend scaffolding
  pass (module conventions, DI container, one request traced end-to-end, events/audit
  fan-out, the AI gateway). Predates the frontend, the care recording engine, and
  everything in section 2 above — treat it as architectural background, not a
  current-state doc.
- **`migrations/README.md`** — Alembic conventions and commands.
- **`governance/`** — `hazard-log.md` (seeded hazards + mitigations, including the
  pseudonymisation gap blocking real LLM use), `dpia-draft.md`, `decision-log.md`
  (why the modular-monolith / ports-and-adapters / audit-immutability decisions were
  made).
