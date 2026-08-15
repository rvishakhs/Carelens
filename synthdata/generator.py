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
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import text, update

from app.shared.security import generate_opaque_token
from synthdata.ai_insights import build_prompt_versions, build_resident_ai_outputs
from synthdata.daily_records import ResidentContext, ResidentDailyState, generate_daily_rows
from synthdata.db import Schema, build_engine, insert_many, insert_rows, tenant_transaction
from synthdata.home_setup import (
    build_activity_occurrences,
    build_admin_user,
    build_care_home,
    build_floors,
    build_staff_users,
    build_user_floor_links,
)
from synthdata.ids import seeded_uuid
from synthdata.keycloak_sync import create_admin_account
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
    "care_plan_goals", "user_resident_links",
]
_DAILY_TABLE_ORDER = [
    "food_intake_records", "fluid_intake_records", "continence_records", "mobility_observations",
    "wellbeing_records", "behaviour_records", "communication_logs", "sleep_records", "vital_signs_records",
    "weight_records", "pain_assessments", "medication_events", "medication_stock_events", "falls_incidents",
    "incidents", "wound_records", "wound_review_notes", "nutrition_risk_assessments",
    "mental_health_assessments", "activity_participation", "visits_log",
    "mobility_assessments", "skin_integrity_assessments", "appointments", "safeguarding_concerns",
]
_AI_TABLE_ORDER = [
    "ai_generation_logs", "resident_ai_summaries", "resident_ai_reports", "resident_ai_alerts", "resident_predictions",
]


@dataclass(frozen=True)
class GenerateResult:
    care_home_id: uuid.UUID
    admin_email: str
    admin_temporary_password: str
    # False when no keycloak_server was given -- the admin row still exists locally,
    # same as every other build_staff_users row, it just can't sign in yet.
    admin_provisioned: bool


def generate(
    *,
    database_url: str,
    care_home_name: str,
    residents: int,
    days: int,
    seed: int,
    staff_count: int = 12,
    admin_email: str = "admin@example-carehome.test",
    admin_password: str | None = None,
    keycloak_server: str = "",
    keycloak_realm: str = "",
    keycloak_client_id: str = "",
    keycloak_client_secret: str = "",
) -> GenerateResult:
    """Generates a full synthetic dataset and returns the care_home_id it was written
    under, plus the bootstrap admin's login. Deterministic via `seed`: same seed +
    args always produces the same dataset (same names, trajectories, values --
    timestamps are relative to "today" minus `days`, so absolute dates shift with the
    run date, everything else doesn't). The admin account is the exception: its
    Keycloak password is regenerated (and re-set on the existing Keycloak account, if
    one from a prior run is still there) every call unless `admin_password` is pinned,
    since a stable secret can't be derived from `seed` alone.
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
            floors = build_floors(rng, care_home_id)
            insert_many(conn, schema, {"floors": floors})
        else:
            floors = [
                dict(row)
                for row in conn.execute(
                    text("SELECT id, floor_type FROM floors WHERE care_home_id = :chi"), {"chi": str(care_home_id)}
                ).mappings()
            ]
        residential_floor_id = next(f["id"] for f in floors if f["floor_type"] == "residential")
        dementia_floor_id = next(f["id"] for f in floors if f["floor_type"] == "dementia")

        # ai_prompt_versions is system-wide reference data with no care_home_id
        # (migration 0016) -- UNIQUE(report_type, version_label) means a rerun against
        # a care home that already exists must not try to recreate rows another run
        # (for this or any other care home) already inserted.
        existing_prompt_versions = [
            dict(row) for row in conn.execute(text("SELECT id, report_type, version_label FROM ai_prompt_versions")).mappings()
        ]
        existing_prompt_keys = {(r["report_type"], r["version_label"]) for r in existing_prompt_versions}
        new_prompt_versions = [
            pv for pv in build_prompt_versions(rng) if (pv["report_type"], pv["version_label"]) not in existing_prompt_keys
        ]
        insert_many(conn, schema, {"ai_prompt_versions": new_prompt_versions})
        prompt_version_ids = {r["report_type"]: r["id"] for r in existing_prompt_versions} | {
            pv["report_type"]: pv["id"] for pv in new_prompt_versions
        }

        staff_users = build_staff_users(rng, care_home_id, staff_count)
        insert_many(conn, schema, {"users": staff_users})
        staff_user_ids = [u["id"] for u in staff_users]
        manager_user_id = next(u["id"] for u in staff_users if u["role"] == "manager")
        nurse_user_ids = [u["id"] for u in staff_users if u["role"] == "nurse"]

        admin_temporary_password = admin_password or generate_opaque_token(9)
        admin_user = build_admin_user(rng, care_home_id, admin_email)
        admin_provisioned = bool(keycloak_server)
        if admin_provisioned:
            admin_user["oidc_subject"] = create_admin_account(
                server_url=keycloak_server,
                realm_name=keycloak_realm,
                client_id=keycloak_client_id,
                client_secret=keycloak_client_secret,
                email=admin_user["email"],
                display_name=admin_user["display_name"],
                role=admin_user["role"],
                temporary_password=admin_temporary_password,
            )
        insert_many(conn, schema, {"users": [admin_user]})

        user_floor_links = build_user_floor_links(rng, care_home_id, [*staff_users, admin_user], floors, manager_user_id)
        insert_many(conn, schema, {"user_floor_links": user_floor_links})

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
            floor_id = dementia_floor_id if persona.cognition == "advanced_dementia" else residential_floor_id

            setup_rows["residents"].append(build_resident_row(persona, care_home_id, resident_id, rng, floor_id=floor_id))

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
                    care_plans=resident_setup["care_plans"],
                    care_plan_goals=resident_setup["care_plan_goals"],
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
        _apply_care_plan_goal_updates(conn, schema, resident_contexts, rng)

        window_end = window_start + timedelta(days=days - 1)
        ai_rows: dict[str, list[dict]] = {name: [] for name in _AI_TABLE_ORDER}
        for ctx in resident_contexts:
            ctx_ai_rows = build_resident_ai_outputs(rng, ctx, prompt_version_ids, window_start, window_end)
            for table_name, rows in ctx_ai_rows.items():
                ai_rows[table_name].extend(rows)
        insert_many(conn, schema, ai_rows)

    return GenerateResult(
        care_home_id=care_home_id,
        admin_email=admin_user["email"],
        admin_temporary_password=admin_temporary_password,
        admin_provisioned=admin_provisioned,
    )


def _apply_wound_updates(conn, schema: Schema, resident_contexts: list[ResidentContext]) -> None:
    """wound_records.status must reflect the *current* status, not just what it was
    at creation -- see ResidentDailyState.wound_updates' docstring."""
    wound_records = schema["wound_records"]
    for ctx in resident_contexts:
        for wound_id, changes in ctx.state.wound_updates.items():
            conn.execute(
                update(wound_records).where(wound_records.c.id == wound_id).values(**changes)
            )


# care_plan_goals.status a resident's trajectory would plausibly drift to over the
# window, keyed by trajectory_name. 'personal' (aspiration) goals aren't clinical, so
# they're drawn from their own distribution below rather than this one.
_GOAL_STATUS_DRIFT = {
    "stable": ["maintained", "maintained", "in_progress"],
    "gradual_decline": ["declining", "declining", "in_progress"],
    "post_fall_recovery": ["improving", "achieved", "maintained"],
    "uti_episode": ["maintained", "improving"],
}
_PERSONAL_GOAL_STATUS_DRIFT = ["in_progress", "improving", "improving", "achieved"]
_VERSION_BUMP_REASONS = {
    "declining": "Goal reviewed: limited progress since last review; plan continues with increased monitoring.",
    "improving": "Goal reviewed: resident showing improvement; plan continues.",
    "achieved": "Goal reviewed: outcome achieved.",
}


def _apply_care_plan_goal_updates(conn, schema: Schema, resident_contexts: list[ResidentContext], rng: random.Random) -> None:
    """care_plan_goals (migration 0020) are seeded at 'in_progress' during setup --
    this drifts each one to a status consistent with how its resident's trajectory
    actually played out, and bumps the parent care_plans row to a new
    care_plan_versions revision wherever that's a materially different status, so
    care_plan_versions carries real revision history instead of only ever v1."""
    care_plan_goals_table = schema["care_plan_goals"]
    care_plans_table = schema["care_plans"]
    new_version_rows: list[dict] = []

    for ctx in resident_contexts:
        plans_by_id = {plan["id"]: plan for plan in ctx.care_plans}
        for goal in ctx.care_plan_goals:
            plan = plans_by_id[goal["care_plan_id"]]
            if plan["domain"] == "personal":
                new_status = rng.choice(_PERSONAL_GOAL_STATUS_DRIFT)
            else:
                new_status = rng.choice(_GOAL_STATUS_DRIFT[ctx.trajectory_name])
            if new_status == goal["status"]:
                continue

            changes: dict = {"status": new_status}
            if new_status == "achieved":
                changes["achieved_date"] = date.today()
            conn.execute(update(care_plan_goals_table).where(care_plan_goals_table.c.id == goal["id"]).values(**changes))

            reason = _VERSION_BUMP_REASONS.get(new_status)
            if reason is None:
                continue
            conn.execute(update(care_plans_table).where(care_plans_table.c.id == plan["id"]).values(current_version=2))
            new_version_rows.append(
                {
                    "id": seeded_uuid(rng),
                    "care_home_id": ctx.care_home_id,
                    "care_plan_id": plan["id"],
                    "version_number": 2,
                    "content": f"{plan['goal']} (Status: {new_status})",
                    "changed_by": rng.choice(ctx.staff_user_ids),
                    "change_reason": reason,
                }
            )

    insert_rows(conn, schema["care_plan_versions"], new_version_rows)
