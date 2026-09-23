"""Create, migrate, test and drop a unique local PostgreSQL database.

Run from intelligence-service: .venv/bin/python scripts/test_outbox_concurrency.py
Requires the existing PostgreSQL Docker container and local .env credentials.
"""

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy.engine import make_url

from intelligence.config import DatabaseSettings, MigrationSettings


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    runtime = make_url(DatabaseSettings().database_url.get_secret_value())
    migrator = make_url(MigrationSettings().migration_database_url.get_secret_value())
    if runtime.host not in {"localhost", "127.0.0.1"}:
        raise RuntimeError("This runner is restricted to local PostgreSQL")
    if (runtime.host, runtime.port) != (migrator.host, migrator.port):
        raise RuntimeError("Runtime and migration connections must target the same server")
    if runtime.username != "intelligence_app" or migrator.username != "intelligence_migrator":
        raise RuntimeError("Expected separate intelligence_app and intelligence_migrator roles")

    container = os.environ.get("INTELLIGENCE_TEST_PG_CONTAINER", "postgres_db")
    name = f"intelligence_test_{uuid4().hex}"

    def admin(sql: str) -> None:
        subprocess.run(
            ["docker", "exec", "-i", container, "sh", "-c",
             'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres'],
            input=sql, text=True, check=True,
        )

    env = os.environ.copy()
    env["INTELLIGENCE_MIGRATION_DATABASE_URL"] = migrator.set(database=name).render_as_string(
        hide_password=False,
    )
    env["INTELLIGENCE_DISPOSABLE_TEST_URL"] = runtime.set(database=name).render_as_string(
        hide_password=False,
    )
    # Also guard against an accidental default connection to the development DB.
    env["INTELLIGENCE_DATABASE_URL"] = env["INTELLIGENCE_DISPOSABLE_TEST_URL"]
    print(f"Disposable database: {name}", flush=True)
    admin(f'CREATE DATABASE "{name}" OWNER intelligence_migrator;')
    try:
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, check=True)
        return subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_outbox_concurrency.py", "--confcutdir=tests", "-q"],
            env=env, check=False,
        ).returncode
    finally:
        # Name is generated here; never drop a database supplied by configuration.
        admin(f'DROP DATABASE "{name}" WITH (FORCE);')
        print(f"Removed disposable database: {name}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
