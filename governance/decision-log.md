# Decision Log

Dated records of architectural/security decisions and the reasoning behind them.
Keeps assessors, buyers, and future-me honest about why the codebase looks the way it
does.

---

## 2026-07-25 -- Modular monolith + ports & adapters, not microservices

**Decision**: Single deployable FastAPI app (`app/`), composed of strictly separated
modules under `app/modules/`, each with a `router.py`/`service.py`/`repository.py`/
`models.py`/`schemas.py`/`ports.py`/`events.py`/`module.py` and exactly one
`register(app, container)` entry point. Modules never import each other's
`repository.py` or `models.py` directly -- only `ports.py` interfaces,
`dependencies.py` factory functions, `schemas.py` DTOs, and `events.py` event
contracts. Cross-cutting concerns (LLM provider, OIDC token verification, event bus,
note structuring, handover attention ranking) are behind abstract ports in
`app/container.py`, with concrete adapters selected by config.

**Why**: Solo-founder pace needs to add/remove features fast without a distributed
systems tax. Module boundaries make later extraction into real services possible
*if* it's ever needed, without paying for it now. Removing a module (e.g.
`medications`) from `ENABLED_MODULES` removes its routes/jobs/events with zero edits
elsewhere -- verified structurally by every module's single `register()` entry point.

**Status**: Implemented as scaffolding for all 8 Phase 1 modules
(`identity`, `residents`, `observations`, `medications`, `audit`, `ai_gateway`,
`summaries`, `handover`). Alembic setup and the actual schema/RLS migrations are
being authored separately (see `migrations/README.md`) -- this scaffold does not
include a working migration yet.

## 2026-07-25 -- Cross-module reads go through Reader ports + bulk methods

**Decision**: Where one module needs read access to another's data (e.g. `handover`
needs residents, observations, and summaries), the owning module exposes an abstract
`XReader` in `ports.py` plus a `get_x_reader()` FastAPI dependency factory in
`dependencies.py`. Readers that get called once per grid row (`ObservationReader`,
`SummaryReader`) also expose a bulk variant (`get_recent_for_residents`,
`get_latest_for_residents`) so the handover view stays at a fixed small number of
queries regardless of resident count, instead of N+1.

**Why**: The architecture doc's <500ms/40-resident handover target can't be hit with
per-resident round trips. Keeping the bulk method on the same port (rather than a
separate bespoke handover-only query module) keeps the "communicate only through
interfaces" rule intact.

**Status**: Implemented for `ResidentReader`, `ObservationReader`, `SummaryReader`.
Not yet verified with `EXPLAIN ANALYZE` against a real 40x90-day dataset -- blocked on
migrations + synthdata actually being run against Postgres.

## 2026-07-25 -- Audit immutability enforced at the DB layer, not the app layer

**Decision**: `audit_events` rows are inserted via `app/modules/audit/repository.py`,
which has no `update()`/`delete()` method by design. The actual guarantee comes from
DB grants (INSERT+SELECT only) and a trigger rejecting UPDATE/DELETE, documented in
`migrations/README.md` for implementation alongside the Alembic migrations.

**Why**: An app-layer-only guarantee doesn't survive a compromised app or a careless
future contributor with direct DB access. The trigger is the actual control; the
missing repository methods are a second layer that fails loudly in code review if
someone tries to add them back.

**Status**: ORM model documents the intent (`app/modules/audit/models.py` docstring);
DB-level enforcement pending the migration described in `migrations/README.md`.

## 2026-07-25 -- LLM provider selection deferred; gateway path proven with dev keys only

**Decision**: `app/modules/ai_gateway/ports.py` defines `LLMProvider` with three
Phase 1 adapters: `FakeLLMProvider` (default, tests/dev), `LocalLLMProvider`
(optional Ollama), and `RealLLMProvider` (raises `NotImplementedError` on `complete()`
until a provider is actually chosen). Real-provider use in Phase 1 is scoped to
proving the pseudonymise -> LLM -> re-identify path end-to-end against synthetic data
only, via dev keys -- never real resident data.

**Why**: Provider choice carries DPA/residency implications that need real
evaluation (Phase 2), but the architecture shouldn't block on that decision --
swapping providers is a `container.py` change, not a refactor.

**Status**: Port + Fake/Local adapters implemented. Real adapter is a stub pending
Phase 2 decision (see `governance/dpia-draft.md` section 9).
