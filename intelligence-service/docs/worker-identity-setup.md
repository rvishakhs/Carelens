# Handover worker identity and CareLens authority

Implemented wiring:

Celery IDs → run_handover_task → Keycloak client credentials → authenticated
CareLens authority reader → execution authorizer → scoped clinical feed → existing
handover gateway → original draft transaction.

The HTTP clients belong to each task's event loop and close on failure or success.
Tokens and client secrets never enter Celery messages. The provider remains the
fake, deterministic provider; unreviewed source text remains blocked.

## 1. Provision a dedicated Keycloak service client

Create a confidential client with service accounts enabled, e.g.
`carelens-intelligence`. Do not reuse the CareLens user-administration client.
Configure an audience mapper so its access tokens contain
`carelens-intelligence-api` in `aud`. The backend requires RS256 signatures,
issuer, audience, expiry, the configured `azp` client ID and the service account's
exact `sub` UUID. The `sub` is the service-account user ID, not the client's internal
UUID or the client ID string. Use Keycloak administration to obtain it.

Choose a token lifetime comfortably above the task's execution budget (for example,
300 seconds). The worker obtains a fresh token each task and rejects tokens with
less than 120 seconds remaining. It does not refresh during a task; expired tokens
are refused by CareLens. Long-running tasks still require the planned lease and
credential lifecycle work.

## 2. Configure the CareLens backend

No database migration is needed for this pilot access registry. In backend secret /
environment configuration, set:

```dotenv
INTELLIGENCE_SERVICE_AUDIENCE=carelens-intelligence-api
INTELLIGENCE_SERVICE_GRANTS=[]
```

The empty list denies all service access. To enroll the pilot, replace it with a JSON
array of registrations in this shape, using actual UUIDs (the placeholders below
are documentation, not valid configuration):

```json
[
  {
    "client_id": "carelens-intelligence",
    "subject": "KEYCLOAK_SERVICE_ACCOUNT_SUB_UUID",
    "service_identity": "intelligence-api",
    "tenant_id": "CARE_HOME_UUID",
    "floor_ids": ["APPROVED_FLOOR_UUID"],
    "resident_ids": ["APPROVED_RESIDENT_UUID"],
    "eligible_resident_ids": ["PILOT_ENROLLED_RESIDENT_UUID"],
    "generating_staff_ids": ["DESIGNATED_STAFF_UUID"],
    "permissions": ["handover:generate"]
  }
]
```

Use one registration per client subject / tenant. Set the backend's existing
`OIDC_ISSUER` to the Keycloak realm issuing these tokens. Supply JSON on one line
when using a dotenv assignment. Keep the identity module enabled.

Registrations are trusted deployment configuration, never accepted from jobs or
public API requests. Updating them requires restarting backend processes because
settings are cached. Staff active status, role permissions, floor links, resident
status and home deletion are read from the DB on requests. A future managed
service-registration repository can replace this pilot configuration without
changing the HTTP contract.

Generation requires both explicit staff designation and the current DB role grants
`view_handover`, `view_resident`, `view_observation`; authorised staff floors are
intersected with the service's configured resident/floor scope. This is generation
permission only: no finalisation permission is created here.

Eligibility is deliberately conservative: explicit pilot enrolment, visible resident,
active resident status, no discharge date, active floor and undeleted care home.
Hospitalised/discharged/archived residents are currently excluded; changing that
pilot policy should be deliberate. Being present in the database is not sufficient.

Add `handover:schedule` only when scheduling is authorised. This does not create
the 07:00/19:00 schedule.

## 3. Configure the intelligence worker

```dotenv
CARELENS_BASE_URL=http://127.0.0.1:8000
INTELLIGENCE_TOKEN_URL=http://127.0.0.1:8080/realms/CareLens/protocol/openid-connect/token
INTELLIGENCE_CLIENT_ID=carelens-intelligence
INTELLIGENCE_CLIENT_SECRET=SET_USING_YOUR_SECRET_STORE
INTELLIGENCE_SERVICE_IDENTITY=intelligence-api
INTELLIGENCE_MINIMUM_TOKEN_LIFETIME_SECONDS=120
```

Keep the existing database and Redis configuration. Match service identity across
submission, the worker, and the backend registration. Outside loopback development,
use HTTPS; redirects and credentials embedded in URLs are rejected. Do not commit
actual secrets or paste tokens into task messages or logs.

Start the worker from `intelligence-service/` after configuration:

```sh
.venv/bin/celery -A intelligence.workers.celery_app:celery_app worker -Q intelligence.handover --loglevel=INFO
```

The registered task `intelligence.handover.generate` takes tenant_id and job_id
strings only. The job must already exist; the task does not create or grant one.
Run the outbox dispatcher alongside the worker to deliver submitted jobs; see
[outbox publishing](outbox-publishing.md) for tenant configuration and commands.

## Read-only backend routes

All require the service bearer token and `tenant_id` query parameter:

- GET /internal/intelligence/authority/service
- GET /internal/intelligence/authority/staff/{actor_id}
- GET /internal/intelligence/authority/residents/{resident_id}/eligibility
- GET /internal/intelligence/observations (resident_id, since, until, limit, offset)

The worker connector selects the last route explicitly. Existing staff routes and
staff authentication are unchanged. Clinical data uses the existing projection and
tenant/floor RLS; no direct intelligence-service access to the CareLens DB is added.
No write or finalisation routes are added.

## Verification and remaining work

Offline verification:

```sh
# CareLens repository root; deliberately avoids the Docker-backed root fixture
.venv/bin/python -B -m pytest --confcutdir=tests/unit/intelligence_service tests/unit/intelligence_service -q -p no:cacheprovider
# From intelligence-service/
.venv/bin/python -B -m pytest --confcutdir=tests tests/unit tests/architecture -q -p no:cacheprovider
```

Tests cover genuine signed token rejection/acceptance, authority refusal and malformed
responses, eligibility, worker dependency injection, HTTP client closure and Celery
argument wiring. Backend unit tests substitute DB sessions; verify the endpoints with
a disposable migrated PostgreSQL instance before real residents. These tests do not
constitute live Keycloak/Redis/PostgreSQL end-to-end validation.

Still outstanding outside this change: live staff authentication on the intelligence
submission API (currently demo scope), lease renewal and failure/retry recovery,
scheduling, care-event retrieval, automatic free-text privacy
processing, live model rollout and nurse-in-charge review/finalisation. A failed
workflow after claiming can still leave a running job until recovery is implemented.
