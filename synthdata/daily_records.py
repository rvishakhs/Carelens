"""Per-day, per-resident time-series generation -- the bulk of the dataset. Reads a
Persona (baseline) and a DailyBias (today's trajectory-driven deviation) and produces
rows for every daily-care-domain table the real schema tracks.

Some domains are periodic rather than daily (vitals, weight, nutrition/mental-health
reassessment, medication stock deliveries) and some carry state across days (an open
wound gets reviewed on subsequent days until it heals) -- both are tracked on
`ResidentDailyState`, one instance per resident, threaded through by generator.py.
"""

import dataclasses
import random
import uuid
from datetime import UTC, date, datetime, time, timedelta

from synthdata.ids import seeded_uuid
from synthdata.notes import generate_note
from synthdata.personas import Persona
from synthdata.trajectories import DailyBias

_MEAL_TIMES: list[tuple[str, time]] = [
    ("breakfast", time(8, 0)),
    ("lunch", time(12, 30)),
    ("dinner", time(17, 30)),
]
_FLUID_ROUND_TIMES = [time(10, 0), time(13, 0), time(15, 30), time(19, 0)]
_BOWEL_TYPES = ["type_1", "type_2", "type_3", "type_4", "type_5", "type_6", "type_7"]
_BEHAVIOUR_TYPES = ["verbal_aggression", "wandering", "resistiveness_to_care", "repetitive_vocalisation", "other"]
_WOUND_LOCATIONS = ["sacrum", "left heel", "right heel", "left elbow", "coccyx"]


@dataclasses.dataclass
class ResidentDailyState:
    """Mutable, per-resident state carried across the whole simulation window."""

    current_weight_kg: float
    visit_day_offset: int = 0
    open_wound_id: uuid.UUID | None = None
    wound_started_day: int = -1
    wound_status_index: int = 0  # index into ("new","improving","static","deteriorating") before healing
    last_weight_day: int = -100
    last_vitals_day: int = -100
    last_nutrition_risk_day: int = -100
    last_mental_health_day: int = -100
    last_stock_delivery_day: int = -100
    last_skin_assessment_day: int = -100
    # wound_id -> latest {"status": ..., "healed_date": date|None} -- applied as an
    # UPDATE against wound_records at the end of the run, since wound_records.status
    # must reflect the *current* status, not just what it was at creation.
    wound_updates: dict[uuid.UUID, dict] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class ResidentContext:
    care_home_id: uuid.UUID
    resident_id: uuid.UUID
    persona: Persona
    medications: list[dict]           # this resident's `medications` rows (with ids)
    staff_user_ids: list[uuid.UUID]
    nurse_user_ids: list[uuid.UUID]
    contacts: list[dict]               # this resident's `resident_contacts` rows
    state: ResidentDailyState
    trajectory_name: str = "stable"


def _at(day: date, t: time) -> datetime:
    return datetime.combine(day, t, tzinfo=UTC)


def generate_daily_rows(
    rng: random.Random,
    ctx: ResidentContext,
    day: date,
    day_index: int,
    is_weekend: bool,
    bias: DailyBias,
    activities_today: list[dict],
) -> dict[str, list[dict]]:
    rows: dict[str, list[dict]] = {name: [] for name in (
        "food_intake_records", "fluid_intake_records", "continence_records", "mobility_observations",
        "wellbeing_records", "behaviour_records", "communication_logs", "sleep_records", "vital_signs_records",
        "weight_records", "pain_assessments", "medication_events", "medication_stock_events", "falls_incidents",
        "incidents", "wound_records", "wound_review_notes", "nutrition_risk_assessments",
        "mental_health_assessments", "activity_participation", "visits_log",
    )}

    recorded_by = lambda: rng.choice(ctx.staff_user_ids)  # noqa: E731

    rows["food_intake_records"] += _food_intake(rng, ctx, day, bias, recorded_by)
    rows["fluid_intake_records"] += _fluid_intake(rng, ctx, day, is_weekend, bias, recorded_by)
    rows["continence_records"] += _continence(rng, ctx, day, bias, recorded_by)
    rows["mobility_observations"] += _mobility_observation(rng, ctx, day, recorded_by)
    rows["wellbeing_records"] += _wellbeing(rng, ctx, day, bias, recorded_by)
    rows["behaviour_records"] += _behaviour(rng, ctx, day, bias, recorded_by)
    rows["communication_logs"] += _communication_log(rng, ctx, day, bias, recorded_by)
    rows["sleep_records"] += _sleep(rng, ctx, day, bias, recorded_by)
    rows["pain_assessments"] += _pain(rng, ctx, day, bias, recorded_by)
    rows["medication_events"] += _medication_events(rng, ctx, day, bias, recorded_by)
    rows["activity_participation"] += _activity_participation(rng, ctx, activities_today, bias, recorded_by)
    rows["visits_log"] += _visit(rng, ctx, day, day_index, bias, recorded_by)

    fall_rows = _falls(rng, ctx, day, bias, recorded_by)
    rows["falls_incidents"] += fall_rows["falls_incidents"]
    rows["incidents"] += fall_rows["incidents"]

    wound_rows = _wounds(rng, ctx, day, day_index, bias, recorded_by)
    rows["wound_records"] += wound_rows["wound_records"]
    rows["wound_review_notes"] += wound_rows["wound_review_notes"]

    # Periodic domains -- not every day.
    if day_index - ctx.state.last_vitals_day >= 7 or bias.fall_today or bias.confusion_spike:
        rows["vital_signs_records"] += _vitals(rng, ctx, day, bias, recorded_by)
        ctx.state.last_vitals_day = day_index

    if day_index - ctx.state.last_weight_day >= 28:
        rows["weight_records"] += _weight(rng, ctx, day, bias, recorded_by)
        ctx.state.last_weight_day = day_index

    if day_index - ctx.state.last_nutrition_risk_day >= 30:
        rows["nutrition_risk_assessments"] += _nutrition_risk(rng, ctx, day, recorded_by)
        ctx.state.last_nutrition_risk_day = day_index

    if ctx.persona.cognition != "intact" and day_index - ctx.state.last_mental_health_day >= 90:
        rows["mental_health_assessments"] += _mental_health(rng, ctx, day, recorded_by)
        ctx.state.last_mental_health_day = day_index

    if day_index - ctx.state.last_stock_delivery_day >= 28:
        rows["medication_stock_events"] += _stock_deliveries(rng, ctx, day, recorded_by)
        ctx.state.last_stock_delivery_day = day_index

    return rows


# --- Nutrition & hydration -----------------------------------------------------

def _food_intake(rng, ctx: ResidentContext, day, bias: DailyBias, recorded_by) -> list[dict]:
    persona = ctx.persona
    rows = []
    for meal_type, meal_time in _MEAL_TIMES:
        if rng.random() < (0.12 if meal_time == _MEAL_TIMES[-1][1] else 0.05):
            continue  # missed/unrecorded meal -- real records are patchy

        refused = rng.random() < persona.refusal_rate * (1.4 if bias.mood in ("agitated", "distressed") else 1.0)
        if refused:
            percentage = 0
            method = "refused"
        else:
            raw = persona.appetite_baseline * bias.appetite_multiplier * rng.uniform(0.85, 1.15)
            percentage = round(max(0.0, min(1.0, raw)) * 100)
            method = _intake_method(rng, persona)

        rows.append(
            {
                "id": seeded_uuid(rng),
                "care_home_id": ctx.care_home_id,
                "resident_id": ctx.resident_id,
                "recorded_at": _at(day, meal_time),
                "recorded_by": recorded_by(),
                "meal_type": meal_type,
                "percentage_eaten": percentage,
                "method": method,
                "texture_modified": "Level 4 - Pureed" if persona.dysphagia and rng.random() < 0.7 else None,
                "notes": None,
            }
        )
    return rows


def _intake_method(rng, persona: Persona) -> str:
    if persona.dysphagia and rng.random() < 0.6:
        return "pureed"
    if persona.mobility_level in ("hoist_dependent", "bed_bound"):
        return rng.choices(["assisted", "fully_fed"], weights=[0.6, 0.4])[0]
    if persona.cognition == "advanced_dementia":
        return rng.choices(["assisted", "independent"], weights=[0.7, 0.3])[0]
    return "independent"


def _fluid_intake(rng, ctx: ResidentContext, day, is_weekend, bias: DailyBias, recorded_by) -> list[dict]:
    persona = ctx.persona
    rows = []
    for round_time in _FLUID_ROUND_TIMES:
        miss_probability = 0.15 if is_weekend else 0.08
        if rng.random() < miss_probability:
            continue
        volume = max(0, int(persona.fluid_baseline_ml / len(_FLUID_ROUND_TIMES) * bias.fluid_multiplier * rng.uniform(0.8, 1.2)))
        rows.append(
            {
                "id": seeded_uuid(rng),
                "care_home_id": ctx.care_home_id,
                "resident_id": ctx.resident_id,
                "recorded_at": _at(day, round_time),
                "recorded_by": recorded_by(),
                "volume_ml": volume,
                "fluid_type": rng.choice(["water", "tea", "juice", "squash"]),
                "thickener_level": "IDDSI Level 2 - Mildly thick" if persona.dysphagia else None,
                "method": _intake_method(rng, persona),
                "notes": None,
            }
        )
    return rows


# --- Continence -----------------------------------------------------------------

def _continence(rng, ctx: ResidentContext, day, bias: DailyBias, recorded_by) -> list[dict]:
    persona = ctx.persona
    if persona.continence_product == "catheter":
        n_events = rng.choice([2, 3])
    else:
        base_events = {"none": 1, "pad": 3, "pull_up": 4, "pad_and_pants": 4}[persona.continence_product]
        n_events = max(1, round(base_events * bias.continence_event_multiplier))

    rows = []
    for i in range(n_events):
        event_time = time((6 + i * (16 // max(n_events, 1))) % 24, rng.choice([0, 15, 30, 45]))
        if persona.continence_product == "catheter":
            event_type = "catheter_care"
        elif persona.continence_product == "none":
            event_type = rng.choices(
                ["continent", "incontinent_urine"], weights=[0.9 / bias.continence_event_multiplier, 0.1 * bias.continence_event_multiplier]
            )[0]
        else:
            event_type = rng.choices(
                ["continent", "incontinent_urine", "incontinent_faeces", "incontinent_both"],
                weights=[0.35, 0.35, 0.1, 0.2],
            )[0]

        bowel_movement = event_type in ("incontinent_faeces", "incontinent_both") or rng.random() < 0.15
        rows.append(
            {
                "id": seeded_uuid(rng),
                "care_home_id": ctx.care_home_id,
                "resident_id": ctx.resident_id,
                "recorded_at": _at(day, event_time),
                "recorded_by": recorded_by(),
                "event_type": event_type,
                "product_used": None if persona.continence_product == "none" else persona.continence_product,
                "bowel_movement": bowel_movement,
                "bristol_type": rng.choice(_BOWEL_TYPES) if bowel_movement else None,
                "urine_output_ml": rng.uniform(100, 400) if event_type.startswith("incontinent") or event_type == "catheter_care" else None,
                "skin_condition": "sore" if bias.skin_risk_elevated and rng.random() < 0.3 else "normal",
                "notes": None,
            }
        )
    return rows


# --- Mobility ---------------------------------------------------------------------

def _mobility_observation(rng, ctx: ResidentContext, day, recorded_by) -> list[dict]:
    persona = ctx.persona
    if rng.random() < 0.3:
        return []
    activity_by_level = {
        "independent": "Walked independently to the dining room",
        "requires_supervision": "Walked to the lounge with supervision",
        "requires_one_assist": "Walked short distance with one carer assisting and a frame",
        "requires_two_assist": "Transferred to wheelchair with two-person assist",
        "hoist_dependent": "Hoisted from bed to chair",
        "bed_bound": "Repositioned in bed",
    }
    return [
        {
            "id": seeded_uuid(rng),
            "care_home_id": ctx.care_home_id,
            "resident_id": ctx.resident_id,
            "recorded_at": _at(day, time(rng.randint(9, 16), 0)),
            "recorded_by": recorded_by(),
            "activity": activity_by_level[persona.mobility_level],
            "distance_or_duration": None,
            "assistance_given": None if persona.mobility_level == "independent" else "One carer",
            "notes": None,
        }
    ]


# --- Behaviour & wellbeing ---------------------------------------------------------

_MOOD_BASELINE = ["content", "settled", "happy"]


def _wellbeing(rng, ctx: ResidentContext, day, bias: DailyBias, recorded_by) -> list[dict]:
    mood = bias.mood or rng.choices(_MOOD_BASELINE + ["anxious"], weights=[0.4, 0.35, 0.15, 0.1])[0]
    engagement = {"agitated": 2, "distressed": 1, "low": 2, "anxious": 3, "withdrawn": 2}.get(mood, rng.randint(3, 5))
    notes = generate_note(mood, bias.appetite_multiplier, bias.fluid_multiplier, rng) if mood not in _MOOD_BASELINE else None
    return [
        {
            "id": seeded_uuid(rng),
            "care_home_id": ctx.care_home_id,
            "resident_id": ctx.resident_id,
            "recorded_at": _at(day, time(11, 0)),
            "recorded_by": recorded_by(),
            "mood": mood,
            "engagement_level": engagement,
            "notes": notes,
        }
    ]


def _behaviour(rng, ctx: ResidentContext, day, bias: DailyBias, recorded_by) -> list[dict]:
    persona = ctx.persona
    if persona.cognition == "intact":
        return []
    trigger = bias.confusion_spike or bias.mood in ("agitated", "distressed") or rng.random() < 0.05
    if not trigger:
        return []
    behaviour_type = rng.choice(_BEHAVIOUR_TYPES)
    return [
        {
            "id": seeded_uuid(rng),
            "care_home_id": ctx.care_home_id,
            "resident_id": ctx.resident_id,
            "occurred_at": _at(day, time(rng.randint(14, 22), rng.choice([0, 30]))),
            "recorded_by": recorded_by(),
            "behaviour_type": behaviour_type,
            "antecedent": rng.choice(["Asked to move to another room", "Personal care attempted", "Unclear trigger", "Noise from another resident"]),
            "behaviour_description": f"Resident became {rng.choice(['verbally', 'physically'])} resistive, {behaviour_type.replace('_', ' ')}.",
            "consequence": rng.choice(["Redirected with reassurance", "Given space and re-approached later", "1:1 support provided"]),
            "duration_minutes": rng.randint(2, 30),
            "triggers_suspected": "Possible UTI or discomfort" if bias.confusion_spike else None,
            "de_escalation_used": "Verbal reassurance, distraction technique",
            "harm_to_self_or_others": rng.random() < 0.05,
        }
    ]


_COMMUNICATION_SUMMARIES = [
    "Chatted about family photos on the wall",
    "Expressed wish to phone a relative, call arranged",
    "Discussed the day's newspaper headlines",
    "Reminisced about their working life",
    "Asked about mealtime plans for the day",
    "Declined to discuss care plan changes today",
]


def _communication_log(rng, ctx: ResidentContext, day, bias: DailyBias, recorded_by) -> list[dict]:
    persona = ctx.persona
    base_rate = 0.35 if persona.communication_method != "verbal" or persona.hearing_impairment else 0.15
    if rng.random() > base_rate:
        return []
    return [
        {
            "id": seeded_uuid(rng),
            "care_home_id": ctx.care_home_id,
            "resident_id": ctx.resident_id,
            "recorded_at": _at(day, time(rng.randint(9, 19), 0)),
            "recorded_by": recorded_by(),
            "interaction_summary": rng.choice(_COMMUNICATION_SUMMARIES),
            "mood_during_interaction": bias.mood or rng.choice(_MOOD_BASELINE),
            "notes": None,
        }
    ]


# --- Sleep --------------------------------------------------------------------------

def _sleep(rng, ctx: ResidentContext, day, bias: DailyBias, recorded_by) -> list[dict]:
    night_wakings = rng.randint(2, 5) if bias.sleep_disruption else rng.randint(0, 2)
    quality = "poor" if night_wakings >= 3 else ("restless" if night_wakings >= 1 else "good")
    return [
        {
            "id": seeded_uuid(rng),
            "care_home_id": ctx.care_home_id,
            "resident_id": ctx.resident_id,
            "night_of": day,
            "recorded_by": recorded_by(),
            "settled_time": time(rng.randint(20, 23), rng.choice([0, 15, 30, 45])),
            "woke_time": time(rng.randint(6, 8), rng.choice([0, 15, 30, 45])),
            "night_wakings": night_wakings,
            "quality": quality,
            "notes": None,
        }
    ]


# --- Vitals & weight ------------------------------------------------------------------

def _vitals(rng, ctx: ResidentContext, day, bias: DailyBias, recorded_by) -> list[dict]:
    systolic = rng.randint(110, 150) + (10 if bias.confusion_spike else 0)
    heart_rate = rng.randint(65, 95) + (15 if bias.confusion_spike or bias.fall_today else 0)
    temperature = round(rng.uniform(36.1, 37.2) + (0.8 if bias.confusion_spike else 0), 1)
    spo2 = rng.randint(94, 99) - (2 if bias.confusion_spike else 0)
    news2 = sum(
        [
            1 if systolic < 111 or systolic > 219 else 0,
            1 if heart_rate > 90 else 0,
            2 if temperature > 38.0 else 0,
            1 if spo2 < 96 else 0,
        ]
    )
    return [
        {
            "id": seeded_uuid(rng),
            "care_home_id": ctx.care_home_id,
            "resident_id": ctx.resident_id,
            "recorded_at": _at(day, time(9, 0)),
            "recorded_by": recorded_by(),
            "blood_pressure_systolic": systolic,
            "blood_pressure_diastolic": rng.randint(65, 90),
            "heart_rate_bpm": heart_rate,
            "respiratory_rate": rng.randint(14, 20),
            "oxygen_saturation_pct": max(85, min(100, spo2)),
            "temperature_celsius": temperature,
            "blood_glucose_mmol": round(rng.uniform(4.5, 8.5), 1),
            "news2_score": news2,
            "notes": "Increased monitoring following fall." if bias.fall_today else None,
        }
    ]


def _weight(rng, ctx: ResidentContext, day, bias: DailyBias, recorded_by) -> list[dict]:
    target = ctx.persona.weight_kg * bias.appetite_multiplier
    ctx.state.current_weight_kg += (target - ctx.state.current_weight_kg) * 0.3 + rng.uniform(-0.3, 0.3)
    return [
        {
            "id": seeded_uuid(rng),
            "care_home_id": ctx.care_home_id,
            "resident_id": ctx.resident_id,
            "recorded_at": _at(day, time(9, 30)),
            "recorded_by": recorded_by(),
            "weight_kg": round(ctx.state.current_weight_kg, 1),
            "height_cm": round(ctx.persona.height_cm, 1),
            "notes": None,
        }
    ]


# --- Pain -----------------------------------------------------------------------------

def _pain(rng, ctx: ResidentContext, day, bias: DailyBias, recorded_by) -> list[dict]:
    if not (bias.pain_flag or rng.random() < 0.04):
        return []
    persona = ctx.persona
    non_verbal = persona.cognition == "advanced_dementia" or persona.communication_method in ("non_verbal",)
    scale_type = "abbey_pain_scale" if non_verbal else "self_report_0_10"
    score = rng.randint(4, 8) if bias.pain_flag else rng.randint(1, 4)
    return [
        {
            "id": seeded_uuid(rng),
            "care_home_id": ctx.care_home_id,
            "resident_id": ctx.resident_id,
            "assessed_at": _at(day, time(rng.randint(10, 20), 0)),
            "assessed_by": recorded_by(),
            "scale_type": scale_type,
            "score": score,
            "location": rng.choice(["lower back", "hip", "left knee", "right shoulder", "general"]),
            "pain_behaviours": "Grimacing, guarding affected area" if non_verbal else None,
            "intervention": "PRN analgesia given" if score >= 4 else "Repositioned, monitored",
            "effective": rng.random() < 0.8 if score >= 4 else None,
            "notes": None,
        }
    ]


# --- Medications ------------------------------------------------------------------------

_CONTROLLED_DRUGS = {"Lorazepam", "Buccal midazolam"}


def _medication_events(rng, ctx: ResidentContext, day, bias: DailyBias, recorded_by) -> list[dict]:
    rows = []
    agitation_today = bias.mood in ("agitated", "distressed") or bias.confusion_spike

    for med in ctx.medications:
        if med["is_prn"]:
            wants_prn = (
                (agitation_today and "for agitation" in (med["prn_indication"] or ""))
                or (bias.pain_flag and "pain" in (med["prn_indication"] or ""))
            )
            if not (wants_prn and rng.random() < 0.7):
                continue
            prn_administered_at = _at(day, time(rng.randint(8, 22), 0))
            rows.append(_medication_event_row(rng, ctx, med, None, prn_administered_at, "administered", recorded_by))
            continue

        for scheduled_time in med["schedule_times"]:
            scheduled_for = _at(day, scheduled_time)
            refusal_chance = ctx.persona.refusal_rate * (1.5 if agitation_today else 1.0)
            roll = rng.random()
            status: str
            administered_at: datetime | None
            if roll < refusal_chance:
                status, administered_at = "refused", None
            elif roll < refusal_chance + 0.02:
                status, administered_at = "omitted", None
            else:
                status, administered_at = "administered", scheduled_for
            rows.append(_medication_event_row(rng, ctx, med, scheduled_for, administered_at, status, recorded_by))
    return rows


def _medication_event_row(rng, ctx, med, scheduled_for, administered_at, status, recorded_by) -> dict:
    administered_by = recorded_by() if status == "administered" else None
    return {
        "id": seeded_uuid(rng),
        "care_home_id": ctx.care_home_id,
        "medication_id": med["id"],
        "resident_id": ctx.resident_id,
        "scheduled_for": scheduled_for,
        "administered_at": administered_at,
        "status": status,
        "reason": None if status == "administered" else "Resident declined" if status == "refused" else "Not available on unit",
        "administered_by": administered_by,
        "witnessed_by": ctx.nurse_user_ids[0] if administered_by and med["drug_name"] in _CONTROLLED_DRUGS and ctx.nurse_user_ids else None,
        "notes": None,
    }


def _stock_deliveries(rng, ctx: ResidentContext, day, recorded_by) -> list[dict]:
    return [
        {
            "id": seeded_uuid(rng),
            "care_home_id": ctx.care_home_id,
            "medication_id": med["id"],
            "event_type": "delivery",
            "quantity_change": rng.randint(28, 56),
            "recorded_by": recorded_by(),
            "notes": "Routine pharmacy delivery.",
        }
        for med in ctx.medications
    ]


# --- Falls & incidents --------------------------------------------------------------------

def _falls(rng, ctx: ResidentContext, day, bias: DailyBias, recorded_by) -> dict[str, list[dict]]:
    if not bias.fall_today:
        return {"falls_incidents": [], "incidents": []}

    severity = rng.choices(["no_injury", "minor_injury", "moderate_injury"], weights=[0.5, 0.35, 0.15])[0]
    occurred_at = _at(day, time(rng.randint(2, 23), rng.choice([0, 15, 30, 45])))
    fall_id = seeded_uuid(rng)
    incident_id = seeded_uuid(rng)
    reporter = recorded_by()

    falls_incidents = [
        {
            "id": fall_id,
            "care_home_id": ctx.care_home_id,
            "resident_id": ctx.resident_id,
            "occurred_at": occurred_at,
            "location": rng.choice(["bedroom", "bathroom", "corridor", "lounge"]),
            "witnessed": rng.random() < 0.4,
            "severity": severity,
            "injuries": None if severity == "no_injury" else "Bruising to hip" if severity == "minor_injury" else "Suspected fracture, sent to hospital",
            "likely_cause": rng.choice(["Loss of balance", "Slipped", "Attempted unassisted transfer", "Unwitnessed"]),
            "action_taken": "GP informed, observations increased" if severity != "moderate_injury" else "Hospital admission arranged",
            "post_fall_observations_required": True,
            "reported_by": reporter,
            "family_informed": rng.random() < 0.85,
        }
    ]
    incidents = [
        {
            "id": incident_id,
            "care_home_id": ctx.care_home_id,
            "resident_id": ctx.resident_id,
            "incident_type": "fall",
            "occurred_at": occurred_at,
            "location": falls_incidents[0]["location"],
            "description": f"Resident found following a fall in the {falls_incidents[0]['location']}.",
            "immediate_action": falls_incidents[0]["action_taken"],
            "reported_by": reporter,
            "riddor_reportable": severity == "moderate_injury",
            "cqc_notifiable": severity in ("moderate_injury", "major_injury"),
            "family_informed": falls_incidents[0]["family_informed"],
            "investigation_status": "closed" if severity == "no_injury" else "in_review",
            "investigation_outcome": None,
        }
    ]
    return {"falls_incidents": falls_incidents, "incidents": incidents}


# --- Skin integrity / wounds -----------------------------------------------------------------

_WOUND_PROGRESSION = ["new", "improving", "static", "deteriorating"]


def _wounds(rng, ctx: ResidentContext, day, day_index, bias: DailyBias, recorded_by) -> dict[str, list[dict]]:
    state = ctx.state
    wound_records: list[dict] = []
    wound_review_notes: list[dict] = []

    if state.open_wound_id is None and bias.skin_risk_elevated and rng.random() < 0.5:
        wound_id = seeded_uuid(rng)
        grade = {"low": "Category 1", "medium": "Category 1", "high": "Category 2", "very_high": "Category 3"}[ctx.persona.skin_risk_baseline]
        wound_records.append(
            {
                "id": wound_id,
                "care_home_id": ctx.care_home_id,
                "resident_id": ctx.resident_id,
                "body_location": rng.choice(_WOUND_LOCATIONS),
                "wound_type": "pressure_ulcer",
                "grade_or_category": grade,
                "length_cm": round(rng.uniform(0.5, 3.0), 1),
                "width_cm": round(rng.uniform(0.5, 2.5), 1),
                "depth_cm": round(rng.uniform(0.1, 1.0), 1),
                "status": "new",
                "treatment_plan": "Pressure-relieving dressing, reposition every 2 hours, review in 7 days.",
                "photo_url": None,
                "first_observed": day,
                "healed_date": None,
            }
        )
        state.open_wound_id = wound_id
        state.wound_started_day = day_index
        state.wound_status_index = 0
        return {"wound_records": wound_records, "wound_review_notes": wound_review_notes}

    if state.open_wound_id is not None and (day_index - state.wound_started_day) % 3 == 0:
        days_open = day_index - state.wound_started_day
        if days_open >= 21:
            status = "healed"
        else:
            state.wound_status_index = min(state.wound_status_index + (1 if rng.random() < 0.6 else 0), len(_WOUND_PROGRESSION) - 1)
            status = _WOUND_PROGRESSION[state.wound_status_index]

        wound_id = state.open_wound_id
        wound_review_notes.append(
            {
                "id": seeded_uuid(rng),
                "care_home_id": ctx.care_home_id,
                "wound_id": wound_id,
                "reviewed_at": _at(day, time(10, 0)),
                "reviewed_by": recorded_by(),
                "status": status,
                "notes": f"Wound {status.replace('_', ' ')} on review.",
                "photo_url": None,
            }
        )
        # wound_records.status must reflect the *current* status, not just what it
        # was at creation -- generator.py applies this as an UPDATE at the end of the
        # run (see ResidentDailyState.wound_updates' docstring).
        state.wound_updates[wound_id] = {"status": status, "healed_date": day if status == "healed" else None}
        if status == "healed":
            state.open_wound_id = None

    return {"wound_records": wound_records, "wound_review_notes": wound_review_notes}


# --- Periodic reassessments -------------------------------------------------------------------

def _nutrition_risk(rng, ctx: ResidentContext, day, recorded_by) -> list[dict]:
    total = rng.randint(0, 6)
    risk_level = "low" if total <= 1 else "medium" if total <= 3 else "high"
    return [
        {
            "id": seeded_uuid(rng),
            "care_home_id": ctx.care_home_id,
            "resident_id": ctx.resident_id,
            "assessment_tool": "MUST",
            "bmi_score": rng.randint(0, 2),
            "weight_loss_score": rng.randint(0, 2),
            "acute_disease_score": rng.randint(0, 2),
            "total_score": total,
            "risk_level": risk_level,
            "action_plan": "Monitor and re-weigh weekly." if risk_level != "low" else None,
            "assessed_by": recorded_by(),
            "assessed_at": _at(day, time(10, 0)),
            "next_review_due": day + timedelta(days=30),
        }
    ]


def _mental_health(rng, ctx: ResidentContext, day, recorded_by) -> list[dict]:
    tool = "Cornell Scale for Depression in Dementia" if ctx.persona.cognition == "advanced_dementia" else "GDS"
    score = rng.randint(0, 20)
    return [
        {
            "id": seeded_uuid(rng),
            "care_home_id": ctx.care_home_id,
            "resident_id": ctx.resident_id,
            "assessment_tool": tool,
            "total_score": score,
            "interpretation": "Within normal range" if score < 8 else "Suggestive of low mood, consider GP review",
            "assessed_by": recorded_by(),
            "assessed_at": _at(day, time(11, 0)),
            "next_review_due": day + timedelta(days=90),
        }
    ]


# --- Activities & visits -----------------------------------------------------------------------

def _activity_participation(rng, ctx: ResidentContext, activities_today, bias: DailyBias, recorded_by) -> list[dict]:
    persona = ctx.persona
    rows = []
    for activity in activities_today:
        base_rate = {"independent": 0.5, "requires_supervision": 0.45, "requires_one_assist": 0.35, "requires_two_assist": 0.25, "hoist_dependent": 0.15, "bed_bound": 0.05}[
            persona.mobility_level
        ]
        if bias.mood in ("agitated", "distressed", "low", "withdrawn"):
            base_rate *= 0.5
        if rng.random() > base_rate:
            continue
        attended = rng.random() < 0.9
        rows.append(
            {
                "id": seeded_uuid(rng),
                "care_home_id": ctx.care_home_id,
                "activity_id": activity["id"],
                "resident_id": ctx.resident_id,
                "attended": attended,
                "engagement_level": rng.randint(1, 5) if attended else None,
                "enjoyment_noted": rng.choice(["Smiled throughout", "Joined in singing", "Seemed to enjoy company"]) if attended and rng.random() < 0.4 else None,
                "recorded_by": recorded_by(),
            }
        )
    return rows


def _visit(rng, ctx: ResidentContext, day, day_index, bias: DailyBias, recorded_by) -> list[dict]:
    if not ctx.contacts or day_index % 7 != ctx.state.visit_day_offset:
        return []
    if rng.random() < 0.6:
        return []
    contact = ctx.contacts[0]
    return [
        {
            "id": seeded_uuid(rng),
            "care_home_id": ctx.care_home_id,
            "resident_id": ctx.resident_id,
            "visitor_name": contact["full_name"],
            "relationship": contact["relationship"],
            "visited_at": _at(day, time(rng.randint(11, 18), 0)),
            "duration_minutes": rng.choice([20, 30, 45, 60]),
            "resident_mood_during_visit": bias.mood or rng.choice(["content", "happy", "settled"]),
            "notes": None,
            "recorded_by": recorded_by(),
        }
    ]
