import pytest


@pytest.fixture(scope="session", autouse=True)
def postgres():
    """Resident-search unit tests use mocked sessions, without PostgreSQL."""
