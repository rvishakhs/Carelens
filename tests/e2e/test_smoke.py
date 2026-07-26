"""The Phase 1 exit-criteria smoke test (see roadmap Week 12 / "Definition of Phase 1
Done"): generate synthetic data -> run the summary job -> fetch the handover view as a
nurse -> assert summary + provenance are visible, and audit rows were written for every
step. Skipped until migrations + testcontainers wiring exist to run it against a real
Postgres instance."""

import pytest

pytestmark = pytest.mark.skip(reason="requires testcontainers Postgres + applied Alembic migrations")


async def test_full_handover_flow_end_to_end():
    # 1. synthdata.generator.generate(residents=5, days=3, seed=1) against the test DB.
    # 2. workers.jobs.summary_job.run_summary_job(container, [care_home_id]).
    # 3. GET /handover as a seeded nurse user -> 200, each card has a latest_summary
    #    with non-empty source_observation_ids.
    # 4. GET /audit as a seeded manager user -> rows exist for resident.created,
    #    observation.recorded, summary.generated, and handover.record_viewed.
    raise NotImplementedError
