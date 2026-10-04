"""Opt-in PostgreSQL test; all inserted records are rolled back."""

import asyncio
import os

import pytest

from scripts.check_tenant_access import main


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("INTELLIGENCE_RUN_DB_TESTS") != "1",
    reason="Set INTELLIGENCE_RUN_DB_TESTS=1 to test local PostgreSQL",
)
def test_tenant_access() -> None:
    asyncio.run(main())
