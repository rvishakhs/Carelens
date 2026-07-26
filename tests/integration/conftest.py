"""Integration tests run against a real Postgres instance via testcontainers, never
SQLite (see production-grade checklist). Add the testcontainers-backed engine/session
fixtures here once Alembic migrations exist to apply against the container.

Sketch:

    from testcontainers.postgres import PostgresContainer

    @pytest.fixture(scope="session")
    def postgres_container():
        with PostgresContainer("postgres:16") as container:
            yield container

    @pytest.fixture
    async def db_session(postgres_container):
        # init_engine(container.get_connection_url()), run `alembic upgrade head`,
        # yield an AsyncSession, roll back after each test.
        ...
"""
