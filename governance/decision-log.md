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

## 2026-07-31 -- Floor authorisation lives in the DB, not in Keycloak claims

**Decision**: `user_floor_links` (migration 0013) is the source of truth for which
floors a user may ever see; it's resolved fresh from the DB on every login
(`app/modules/identity/dependencies.py`), not carried as a JWT claim. The session GUC
`app.floor_ids` (set via `rls_session()`) is populated from this DB lookup, currently
"every floor the user is authorised for" -- there's no floor-picker UI yet, so a
session requests everything it's allowed to see by default.

**Why**: Keycloak is good at "who is this and what's their role", not at "which of
this home's floors can they see today" -- that's operational, home-specific data that
changes independently of identity (a manager grants/revokes it via `floors`' own
endpoints, `POST/DELETE /floors/access`). Putting it in a token would mean revoking
access doesn't take effect until the token expires; reading it fresh from the DB means
it's immediate.

**Status**: Implemented. `KeycloakTokenVerifier` deliberately does not look for a
floor claim.

## 2026-08-03 -- care_home_id resolved from the local `users` table, not the JWT

**Decision**: `TokenClaims` (identity/ports.py) no longer carries `care_home_id`.
`KeycloakTokenVerifier` reads only identity claims (`sub`, `email`/`name`, `role`).
`get_current_user` (identity/dependencies.py) resolves the tenant itself: a
`bootstrap_session()` (app/shared/database.py) looks up `care_home_id` from `users`
by `oidc_subject`, then opens the normal tenant-scoped `rls_session()` for everything
else. `UserRepository.sync_from_claims` no longer JIT-creates a user from a bare
token -- it 401s if no local row exists yet. A local row is created ahead of time
instead, by a manager's "add staff" flow (`POST /identity/staff`,
`IdentityService.create_staff_member`), which provisions the Keycloak account via
the new `IdentityProviderAdmin` port (`adapters/keycloak_admin.py`, backed by
`python-keycloak`'s async admin client) and the local mirror row together, atomically
enough for a single-care-home deployment.

**Why**: Keycloak is good at "who is this" (identity), not at "which of our tenants
do they belong to and what can they do inside it" (application/tenant data) -- that's
CareLens's own concern, and folding it into a JWT claim meant moving someone between
care homes (or fixing a mis-provisioned one) wouldn't take effect until their token
expired. This mirrors the same reasoning already applied to floor authorisation (see
the entry below) -- `care_home_id` is just a coarser-grained version of the same
problem. The tradeoff is a genuine bootstrap problem: `users` is tenant-scoped RLS
like everything else, so a session that doesn't know `care_home_id` yet can't read
the very row that would tell it. `bootstrap_session()` / the `identity_bootstrap_select`
policy (migration 0019) is the narrow, explicit fix -- not a bypass-RLS DB role, kept
in one place, and the calling code only ever uses it for a single-row lookup by
`oidc_subject`.

**Status**: Implemented. `identity/router.py` exposes `POST/GET /identity/staff`
(manager-only, `MANAGE_USERS`) restricted to provisioning `carer`/`nurse` roles --
higher-privilege roles aren't handed out through this flow yet.

## 2026-07-31 -- Expected Keycloak realm setup (for when that work starts)

Recorded here so the realm config and this code agree on contract, without either
having been built yet in lockstep:

- **Not a claim**: `care_home_id` -- see the 2026-08-03 entry above. Resolved from
  the local `users` table instead; no protocol mapper needed for it.
- **Role, one of two shapes**: either a custom `role` claim (single string, exactly
  one of `app.modules.identity.models.Role`'s values: `carer`, `nurse`, `manager`,
  `family`, `emergency`, `system_admin`, `admin`, `headoffice`) -- simplest, one
  protocol mapper, one attribute per user. Or, without any custom mapper, assign the
  matching realm role (same value strings) to the user and rely on Keycloak's default
  `realm_access.roles` claim -- `KeycloakTokenVerifier._extract_role()` intersects
  that array against known Role values and requires exactly one match, erroring
  clearly if zero or more than one are present. Don't do both (custom claim wins
  silently if present) and don't assign more than one of this app's realm roles to a
  single user.
- **MFA**: enforced by Keycloak's own authentication flow/policy for staff roles
  (carer/nurse/manager/admin/headoffice/system_admin), not by this app -- there is
  nothing in `KeycloakTokenVerifier` that checks an MFA claim; if MFA needs to be
  provable per-session later (e.g. for `emergency_access` audit entries), that's a new
  claim + a new check, not implemented yet.
- **Floor access**: intentionally NOT a Keycloak concern -- see the decision above.
- **Realm export**: once the realm is built, commit its export alongside
  `docker-compose.yml` (the `keycloak` service already has a commented-out volume
  mount pointing at `./identity/keycloak-realm-export.json`, waiting for this file to
  exist) so `docker compose up` reproduces the same realm for anyone cloning the repo.
