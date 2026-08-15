"""Read-only aggregation queries spanning the ~15 clinical/care-planning tables that
have no ORM model (they only ever existed as migration DDL + synthdata's
reflection-based inserts -- see governance/decision-log.md context from the synthdata
expansion). Raw SQL rather than a model per table: these are display-only reads, run
through the same RLS-scoped AsyncSession every other repository in this app uses, so
tenant/floor filtering is already enforced by Postgres -- no `care_home_id`/`floor_id`
filters needed in the SQL itself.
"""

import uuid
from collections import defaultdict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.residents.schemas import (
    ActivityEntry,
    AdvanceDirectiveRead,
    AllergyRead,
    CarePlanGoalRead,
    CarePlanRead,
    CareRecordEntry,
    ContactRead,
    DiagnosisRead,
    LifeHistoryRead,
    PreferenceRead,
    ResidentListItem,
    ResidentOverview,
    VitalsSnapshot,
    WeightPoint,
)

_LIST_SQL = """
SELECT
    r.id, r.first_name, r.last_name, r.preferred_name, r.date_of_birth, r.gender,
    r.room_number, r.floor_id, f.name AS floor_name, r.status,
    EXISTS (
        SELECT 1 FROM advance_care_directives d
        WHERE d.resident_id = r.id AND d.directive_type = 'DNACPR' AND d.is_current
    ) AS dnacpr,
    EXISTS (SELECT 1 FROM resident_allergies a WHERE a.resident_id = r.id) AS has_allergies,
    EXISTS (
        SELECT 1 FROM resident_diagnoses dg
        WHERE dg.resident_id = r.id AND dg.status = 'active' AND dg.condition_name ILIKE '%diabetes%'
    ) AS diabetic,
    coalesce(
        (SELECT array_agg(DISTINCT cp.domain::text) FROM care_plans cp WHERE cp.resident_id = r.id AND cp.is_active),
        ARRAY[]::text[]
    ) AS active_care_domains,
    GREATEST(
        (SELECT max(recorded_at) FROM wellbeing_records w WHERE w.resident_id = r.id),
        (SELECT max(recorded_at) FROM vital_signs_records v WHERE v.resident_id = r.id),
        (SELECT max(recorded_at) FROM food_intake_records fi WHERE fi.resident_id = r.id)
    ) AS last_activity_at
FROM residents r
LEFT JOIN floors f ON f.id = r.floor_id
WHERE r.status = 'active' AND r.deleted_at IS NULL
ORDER BY r.room_number
"""

_TIMELINE_SQL = """
SELECT id, 'food_intake' AS record_type, recorded_at, ('Food: ' || meal_type::text) AS title, (percentage_eaten::text || '% eaten') AS detail
FROM food_intake_records WHERE resident_id = :rid
UNION ALL
SELECT id, 'fluid_intake', recorded_at, 'Fluid intake', (volume_ml::text || 'ml ' || fluid_type)
FROM fluid_intake_records WHERE resident_id = :rid
UNION ALL
SELECT id, 'continence', recorded_at, ('Continence: ' || event_type::text), coalesce(skin_condition, '')
FROM continence_records WHERE resident_id = :rid
UNION ALL
SELECT id, 'mobility', recorded_at, 'Mobility', activity
FROM mobility_observations WHERE resident_id = :rid
UNION ALL
SELECT id, 'wellbeing', recorded_at, ('Wellbeing: ' || mood::text), coalesce(notes, '')
FROM wellbeing_records WHERE resident_id = :rid
UNION ALL
SELECT id, 'behaviour', occurred_at, ('Behaviour: ' || behaviour_type::text), behaviour_description
FROM behaviour_records WHERE resident_id = :rid
UNION ALL
SELECT id, 'communication', recorded_at, 'Communication', interaction_summary
FROM communication_logs WHERE resident_id = :rid
UNION ALL
SELECT id, 'sleep', night_of::timestamptz, ('Sleep: ' || quality::text), (night_wakings::text || ' wakings')
FROM sleep_records WHERE resident_id = :rid
UNION ALL
SELECT id, 'vitals', recorded_at, 'Vital signs', ('NEWS2 ' || coalesce(news2_score::text, 'n/a'))
FROM vital_signs_records WHERE resident_id = :rid
UNION ALL
SELECT id, 'weight', recorded_at, 'Weight recorded', (weight_kg::text || 'kg')
FROM weight_records WHERE resident_id = :rid
UNION ALL
SELECT id, 'pain', assessed_at, 'Pain assessment', ('Score ' || score::text)
FROM pain_assessments WHERE resident_id = :rid
UNION ALL
SELECT id, 'falls', occurred_at, ('Fall: ' || severity::text), location
FROM falls_incidents WHERE resident_id = :rid
UNION ALL
SELECT id, 'incident', occurred_at, ('Incident: ' || incident_type::text), description
FROM incidents WHERE resident_id = :rid
UNION ALL
SELECT id, 'wound', first_observed::timestamptz, ('Wound: ' || wound_type::text), status::text
FROM wound_records WHERE resident_id = :rid
ORDER BY recorded_at DESC
LIMIT 40
"""

_ACTIVITY_SQL = """
SELECT ap.id, 'activity' AS entry_type, a.scheduled_at AS occurred_at, a.name AS title,
       CASE WHEN ap.attended THEN 'Attended' ELSE 'Did not attend' END AS detail
FROM activity_participation ap JOIN activities a ON a.id = ap.activity_id
WHERE ap.resident_id = :rid
UNION ALL
SELECT id, 'visit', visited_at, ('Visit from ' || visitor_name), relationship
FROM visits_log WHERE resident_id = :rid
UNION ALL
SELECT id, 'appointment', scheduled_at, ('Appointment: ' || appointment_type::text), reason
FROM appointments WHERE resident_id = :rid
ORDER BY occurred_at DESC
LIMIT 40
"""


class ResidentDetailRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_with_summary(self) -> list[ResidentListItem]:
        rows = (await self._session.execute(text(_LIST_SQL))).mappings().all()
        return [ResidentListItem(**row) for row in rows]

    async def get_overview(self, resident_id: uuid.UUID) -> ResidentOverview | None:
        resident_exists = (
            await self._session.execute(
                text("SELECT 1 FROM residents WHERE id = :rid AND deleted_at IS NULL"), {"rid": resident_id}
            )
        ).scalar_one_or_none()
        if resident_exists is None:
            return None

        diagnoses = (
            await self._session.execute(
                text(
                    "SELECT id, condition_name, icd10_code, diagnosed_date, is_primary, status, notes "
                    "FROM resident_diagnoses WHERE resident_id = :rid ORDER BY is_primary DESC, diagnosed_date"
                ),
                {"rid": resident_id},
            )
        ).mappings().all()

        allergies = (
            await self._session.execute(
                text("SELECT id, allergen, reaction, severity FROM resident_allergies WHERE resident_id = :rid"),
                {"rid": resident_id},
            )
        ).mappings().all()

        contacts = (
            await self._session.execute(
                text(
                    "SELECT id, full_name, relationship, is_next_of_kin, is_emergency_contact, phone, email "
                    "FROM resident_contacts WHERE resident_id = :rid ORDER BY is_next_of_kin DESC"
                ),
                {"rid": resident_id},
            )
        ).mappings().all()

        directives = (
            await self._session.execute(
                text(
                    "SELECT id, directive_type, summary, review_due, is_current FROM advance_care_directives "
                    "WHERE resident_id = :rid AND is_current"
                ),
                {"rid": resident_id},
            )
        ).mappings().all()

        life_history = (
            await self._session.execute(
                text(
                    "SELECT occupation, family_background, significant_events, hobbies_interests, "
                    "important_relationships, faith_religion, cultural_background, military_veteran, free_text_narrative "
                    "FROM resident_life_history WHERE resident_id = :rid LIMIT 1"
                ),
                {"rid": resident_id},
            )
        ).mappings().first()

        preferences = (
            await self._session.execute(
                text(
                    "SELECT category, preference, is_like, priority FROM resident_preferences "
                    "WHERE resident_id = :rid ORDER BY priority DESC LIMIT 8"
                ),
                {"rid": resident_id},
            )
        ).mappings().all()

        latest_vitals = (
            await self._session.execute(
                text(
                    "SELECT recorded_at, blood_pressure_systolic, blood_pressure_diastolic, heart_rate_bpm, "
                    "oxygen_saturation_pct, temperature_celsius, news2_score FROM vital_signs_records "
                    "WHERE resident_id = :rid ORDER BY recorded_at DESC LIMIT 1"
                ),
                {"rid": resident_id},
            )
        ).mappings().first()

        weight_trend = (
            await self._session.execute(
                text(
                    "SELECT recorded_at, weight_kg FROM weight_records WHERE resident_id = :rid "
                    "ORDER BY recorded_at DESC LIMIT 12"
                ),
                {"rid": resident_id},
            )
        ).mappings().all()

        mobility = (
            await self._session.execute(
                text(
                    "SELECT mobility_level, falls_risk_level FROM mobility_assessments WHERE resident_id = :rid "
                    "ORDER BY assessed_at DESC LIMIT 1"
                ),
                {"rid": resident_id},
            )
        ).mappings().first()

        skin = (
            await self._session.execute(
                text(
                    "SELECT risk_level FROM skin_integrity_assessments WHERE resident_id = :rid "
                    "ORDER BY assessed_at DESC LIMIT 1"
                ),
                {"rid": resident_id},
            )
        ).mappings().first()

        active_medication_count = (
            await self._session.execute(
                text("SELECT count(*) FROM medications WHERE resident_id = :rid AND is_active"), {"rid": resident_id}
            )
        ).scalar_one()

        return ResidentOverview(
            resident_id=resident_id,
            diagnoses=[DiagnosisRead(**d) for d in diagnoses],
            allergies=[AllergyRead(**a) for a in allergies],
            contacts=[ContactRead(**c) for c in contacts],
            advance_directives=[AdvanceDirectiveRead(**d) for d in directives],
            life_history=LifeHistoryRead(**life_history) if life_history else None,
            top_preferences=[PreferenceRead(**p) for p in preferences],
            latest_vitals=VitalsSnapshot(**latest_vitals) if latest_vitals else None,
            weight_trend=list(reversed([WeightPoint(**w) for w in weight_trend])),
            mobility_level=mobility["mobility_level"] if mobility else None,
            falls_risk_level=mobility["falls_risk_level"] if mobility else None,
            skin_risk_level=skin["risk_level"] if skin else None,
            active_medication_count=active_medication_count,
            dnacpr=any(d["directive_type"] == "DNACPR" for d in directives),
        )

    async def get_care_plan(self, resident_id: uuid.UUID) -> list[CarePlanRead]:
        plans = (
            await self._session.execute(
                text(
                    "SELECT id, domain, goal, is_active, review_due FROM care_plans "
                    "WHERE resident_id = :rid AND is_active ORDER BY domain"
                ),
                {"rid": resident_id},
            )
        ).mappings().all()
        if not plans:
            return []

        goals = (
            await self._session.execute(
                text(
                    "SELECT id, care_plan_id, goal_text, baseline, target, measurement, status, review_date "
                    "FROM care_plan_goals WHERE care_plan_id IN ("
                    "    SELECT id FROM care_plans WHERE resident_id = :rid AND is_active"
                    ")"
                ),
                {"rid": resident_id},
            )
        ).mappings().all()

        goals_by_plan: dict[uuid.UUID, list[CarePlanGoalRead]] = defaultdict(list)
        for g in goals:
            goals_by_plan[g["care_plan_id"]].append(
                CarePlanGoalRead(
                    id=g["id"], goal_text=g["goal_text"], baseline=g["baseline"], target=g["target"],
                    measurement=g["measurement"], status=g["status"], review_date=g["review_date"],
                )
            )

        return [
            CarePlanRead(
                id=p["id"], resident_id=resident_id, domain=p["domain"], goal=p["goal"], is_active=p["is_active"],
                review_due=p["review_due"], goals=goals_by_plan.get(p["id"], []),
            )
            for p in plans
        ]

    async def get_care_records(self, resident_id: uuid.UUID) -> list[CareRecordEntry]:
        rows = (await self._session.execute(text(_TIMELINE_SQL), {"rid": resident_id})).mappings().all()
        return [CareRecordEntry(**row) for row in rows]

    async def get_activity(self, resident_id: uuid.UUID) -> list[ActivityEntry]:
        rows = (await self._session.execute(text(_ACTIVITY_SQL), {"rid": resident_id})).mappings().all()
        return [ActivityEntry(**row) for row in rows]

    async def list_active_care_plans(self) -> list[CarePlanRead]:
        """Home-wide, for CarePlansPage -- every active care plan across every
        resident, each with its goals. Same shape as get_care_plan, just not
        filtered to one resident_id."""
        plans = (
            await self._session.execute(
                text("SELECT id, resident_id, domain, goal, is_active, review_due FROM care_plans WHERE is_active ORDER BY resident_id, domain")
            )
        ).mappings().all()
        if not plans:
            return []

        goals = (
            await self._session.execute(
                text(
                    "SELECT id, care_plan_id, goal_text, baseline, target, measurement, status, review_date "
                    "FROM care_plan_goals WHERE care_plan_id IN (SELECT id FROM care_plans WHERE is_active)"
                )
            )
        ).mappings().all()

        goals_by_plan: dict[uuid.UUID, list[CarePlanGoalRead]] = defaultdict(list)
        for g in goals:
            goals_by_plan[g["care_plan_id"]].append(
                CarePlanGoalRead(
                    id=g["id"], goal_text=g["goal_text"], baseline=g["baseline"], target=g["target"],
                    measurement=g["measurement"], status=g["status"], review_date=g["review_date"],
                )
            )

        return [
            CarePlanRead(
                id=p["id"], resident_id=p["resident_id"], domain=p["domain"], goal=p["goal"],
                is_active=p["is_active"], review_due=p["review_due"], goals=goals_by_plan.get(p["id"], []),
            )
            for p in plans
        ]
