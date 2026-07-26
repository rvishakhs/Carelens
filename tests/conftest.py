"""Shared pytest fixtures. Unit tests (tests/unit/) should never need a database.
Integration/RBAC/e2e tests need a real Postgres instance via testcontainers -- SQLite
is never substituted, per the production-grade checklist."""

import os

os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
