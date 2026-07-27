"""Orchestrates personas + trajectories + setup/daily record builders into a full
synthetic dataset, written straight into the live Postgres schema your Alembic
migrations created (via table reflection in db.py -- see its docstring for why).

The whole run is one transaction: if anything fails partway, nothing is left
half-written, which also makes re-running with the same --seed idempotent-by-retry
(drop the care home, run again, get byte-for-byte the same dataset).
"""

import random
import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import text, update

from synthdata.daily_records import ResidentContext, ResidentDailyState, generate_daily_rows
from synthdata.db import Schema, build_engine, insert_many, tenant_transaction
from synthdata.home_setup import build_activity_occurrences, build_care_home, build_staff_users
from synthdata.ids import seeded_uuid
from synthdata.personas import generate_persona
from synthdata.setup_records import build_resident_row, build_resident_setup
from synthdata.trajectories import TRAJECTORIES

# Placeholder actor for the RLS `app.user_id` GUC -- matches the convention used by
# app/modules/audit/module.py and workers/jobs/summary_job.py for non-human actors.
_SYSTEM_ACTOR = uuid.UUID(int=0)

_TRAJECTORY_WEIGHTS = [0.55, 0.2, 0.15, 0.1]  # stable, gradual_decline, post_fall_recovery, uti_episode

# Table insertion order matters: FKs must land before the rows that reference them.
_SETUP_TABLE_ORDER = [
    "users", "residents", "resident_contacts", "resident_consents", "resident_life_history",
    "resident_preferences", "resident_daily_routines", "resident_allergies", "resident_diagnoses",
    "advance_care_directives", "communication_needs", "continence_care_plans", "nutrition_hydration_targets",
    "mobility_assessments", "skin_integrity_assessments", "medications", "care_plans", "care_plan_versions",
    "user_resident_links",
]
_DAILY_TABLE_ORDER = [
    "food_intake_records", "fluid_intake_records", "continence_records", "mobility_observations",
    "wellbeing_records", "behaviour_records", "communication_logs", "sleep_records", "vital_signs_records",
    "weight_records", "pain_assessments", "medication_events", "medication_stock_events", "falls_incidents",
    "incidents", "wound_records", "wound_review_notes", "nutrition_risk_assessments",
    "mental_health_assessments", "activity_participation", "visits_log",
]


def generate(
    *,
    database_url: str,
    care_home_name: str,
    residents: int,
    days: int,
    seed: int,
    staff_count: int = 12,
) -> uuid.UUID:
    """Generates a full synthetic dataset and returns the care_home_id it was written
    under. Deterministic via `seed`: same seed + args always produces the same
    dataset (same names, trajectories, values -- timestamps are relative to "today"
    minus `days`, so absolute dates shift with the run date, everything else doesn't).
    """
    rng = random.Random(seed)
    window_start = date.today() - timedelta(days=days)

    engine = build_engine(database_url)
    schema = Schema(engine)

    with engine.begin() as conn:
        existing = conn.execute(
            text(
                """
                SELECT id
                FROM care_homes
                WHERE name = :name LIMIT 1
                """
            ),
            {"name": care_home_name},
        ).scalar_one_or_none()

    care_home_id: uuid.UUID
    if existing:
        care_home_id = existing
        create_care_home = False
    else:
        care_home = build_care_home(rng, care_home_name)
        care_home_id = care_home["id"]
        create_care_home = True

    with tenant_transaction(engine, care_home_id, _SYSTEM_ACTOR) as conn:
        if create_care_home:
            insert_many(conn, schema, {"care_homes": [care_home]})

        staff_users = build_staff_users(rng, care_home_id, staff_count)
        insert_many(conn, schema, {"users": staff_users})
        staff_user_ids = [u["id"] for u in staff_users]
        manager_user_id = next(u["id"] for u in staff_users if u["role"] == "manager")
        nurse_user_ids = [u["id"] for u in staff_users if u["role"] == "nurse"]

        activity_occurrences = build_activity_occurrences(rng, care_home_id, window_start, days)
        insert_many(conn, schema, {"activities": activity_occurrences})
        activities_by_day: dict[date, list[dict]] = defaultdict(list)
        for occurrence in activity_occurrences:
            activities_by_day[occurrence["scheduled_at"].date()].append(occurrence)

        setup_rows: dict[str, list[dict]] = {name: [] for name in _SETUP_TABLE_ORDER}
        daily_rows: dict[str, list[dict]] = {name: [] for name in _DAILY_TABLE_ORDER}
        resident_contexts: list[ResidentContext] = []

        for _ in range(residents):
            persona = generate_persona(rng, window_start=window_start)
            resident_id = seeded_uuid(rng)

            setup_rows["residents"].append(build_resident_row(persona, care_home_id, resident_id, rng))

            resident_setup, medication_ids = build_resident_setup(
                rng,
                care_home_id=care_home_id,
                resident_id=resident_id,
                persona=persona,
                staff_user_ids=staff_user_ids,
                manager_user_id=manager_user_id,
                window_start=window_start,
            )
            for table_name, rows in resident_setup.items():
                setup_rows[table_name].extend(rows)

            state = ResidentDailyState(current_weight_kg=persona.weight_kg, visit_day_offset=rng.randint(0, 6))
            trajectory_name = rng.choices(list(TRAJECTORIES.keys()), weights=_TRAJECTORY_WEIGHTS)[0]
            resident_contexts.append(
                ResidentContext(
                    care_home_id=care_home_id,
                    resident_id=resident_id,
                    persona=persona,
                    medications=resident_setup["medications"],
                    staff_user_ids=staff_user_ids,
                    nurse_user_ids=nurse_user_ids,
                    contacts=resident_setup["resident_contacts"],
                    state=state,
                    trajectory_name=trajectory_name,
                )
            )

        insert_many(conn, schema, setup_rows)

        for ctx in resident_contexts:
            trajectory = TRAJECTORIES[ctx.trajectory_name](rng, days)
            for day_index in range(days):
                day = window_start + timedelta(days=day_index)
                is_weekend = day.weekday() >= 5
                bias = trajectory.bias_for_day(day_index, days, rng)
                activities_today = activities_by_day.get(day, [])

                day_rows = generate_daily_rows(rng, ctx, day, day_index, is_weekend, bias, activities_today)
                for table_name, rows in day_rows.items():
                    daily_rows[table_name].extend(rows)

        insert_many(conn, schema, daily_rows)
        _apply_wound_updates(conn, schema, resident_contexts)

    return care_home_id


def _apply_wound_updates(conn, schema: Schema, resident_contexts: list[ResidentContext]) -> None:
    """wound_records.status must reflect the *current* status, not just what it was
    at creation -- see ResidentDailyState.wound_updates' docstring."""
    wound_records = schema["wound_records"]
    for ctx in resident_contexts:
        for wound_id, changes in ctx.state.wound_updates.items():
            conn.execute(
                update(wound_records).where(wound_records.c.id == wound_id).values(**changes)
            )
