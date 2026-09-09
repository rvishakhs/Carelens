# Skeleton verification

Verified in the independent service virtual environment, using its resolved `uv.lock`.

| Check | Result |
|---|---|
| Isolated pytest suite | 21 passed |
| Ruff checks and formatting | Passed |
| Strict mypy over service package | Passed, 20 source files |
| Locked dependency installation | Passed in this project's own `.venv`; CareLens dependencies not modified |
| Standalone distribution build | Wheel and source distribution built successfully |
| Real loopback HTTP smoke | Uvicorn started on an unused local port; both agents returned expected 450 ml consumed / 630 ml offered; process stopped afterward |
| Compose configuration | `docker compose config --quiet` passed |
| OpenAPI | Exported to `docs/openapi.json`; live explorer at `/docs` |
| Whitespace | `git diff --check` passed |

Tests cover authentication, strict request validation without echoed payloads, resident/tenant scope, current result-read scope and permission checks, result expiry/capacity, period boundaries, missing versus zero, gateway outbound structure, rejected aliases/citations/numbers, and fake-only configuration. An import boundary check prohibits CareLens `app` imports and real provider SDK imports in the skeleton.

Two third-party test-client deprecation warnings remain: Starlette's HTTPX transition and an AnyIO portal alias. They are not test failures. No application-wide regression suite was rerun because no CareLens runtime code changed for this skeleton.

Docker image build/container execution, production deployment, PostgreSQL/Temporal integration, real provider use, all 14 live sources and the clinical pilot evaluation pack were **not** tested by these checks. The 21 scaffold tests are not the P0-07/P0-08 clinical evaluation.

No paid model calls, resident-data ingestion or cloud resources were used. A local ignored `.env` with a random synthetic demo token was generated; the token was not printed. The service was stopped after the HTTP smoke; it is not left running.
