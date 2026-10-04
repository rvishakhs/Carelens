from pydantic import SecretStr

from intelligence.config import DatabaseSettings, MigrationSettings


def test_migrations_use_dedicated_credentials_without_demo_token(monkeypatch):
    monkeypatch.setenv("INTELLIGENCE_DATABASE_URL", "postgresql+psycopg://intelligence_app@localhost/test")
    monkeypatch.setenv(
        "INTELLIGENCE_MIGRATION_DATABASE_URL", "postgresql+psycopg://intelligence_migrator@localhost/test"
    )
    runtime = DatabaseSettings(_env_file=None)
    migration = MigrationSettings(_env_file=None)
    assert runtime.database_url == SecretStr("postgresql+psycopg://intelligence_app@localhost/test")
    assert migration.migration_database_url == SecretStr(
        "postgresql+psycopg://intelligence_migrator@localhost/test"
    )
