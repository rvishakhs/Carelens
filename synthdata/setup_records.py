"""One-time, per-resident setup rows -- everything that describes who a resident is
and what their baseline care plan looks like, as opposed to what happened on a given
day (that's daily_records.py). Called once per resident during generation.
"""

import random
import uuid
from datetime import UTC, date, datetime, time, timedelta

from synthdata.home_setup import build_family_user, random_family_relationship
from synthdata.ids import seeded_uuid
from synthdata.personas import Persona
from synthdata.reference_data import (
    ALLERGENS,
    CULTURAL_BACKGROUNDS,
    DIAGNOSES,
    DIRECTIVE_TYPES,
    FAITHS,
    FAMILY_BACKGROUND_SNIPPETS,
    HOBBIES,
    IMPORTANT_RELATIONSHIPS_SNIPPETS,
    OCCUPATIONS,
    PERSONAL_ASPIRATIONS,
    PREFERENCE_ITEMS,
    PRN_MEDICATIONS,
    REGULAR_MEDICATIONS,
    SIGNIFICANT_EVENTS_SNIPPETS,
)

_CARE_PLAN_GOALS: dict[str, str] = {
    "nutrition_hydration": "Maintain adequate nutrition and hydration; monitor intake and escalate if refusal persists beyond 2 consecutive meals.",
    "mobility": "Support safe mobility with appropriate aids/assistance; minimise falls risk.",
    "continence": "Maintain skin integrity and dignity through a consistent continence care regime.",
    "communication": "Support effective communication using the resident's preferred method; involve family where helpful.",
    "behaviour_wellbeing": "Promote wellbeing and reduce distress through person-centred, consistent responses to behaviour.",
    "skin_integrity": "Prevent pressure damage through regular repositioning and equipment use; escalate any new skin concerns promptly.",
    "medication": "Ensure medications are administered safely and as prescribed; monitor for refusal or side effects.",
    "sleep": "Support restful sleep through a consistent night routine; monitor and escalate persistent disturbance.",
    "pain_management": "Recognise and manage pain promptly, including for residents unable to self-report.",
    "social_activities": "Support engagement in meaningful social and recreational activity in line with preferences.",
    "end_of_life": "Provide comfort-focused, dignified care in line with the resident's advance wishes.",
}


# baseline/target/measurement per domain, for the structured care_plan_goals row
# underneath each care_plans row (migration 0020) -- care_plans.goal stays the
# free-text "what are we doing"; this is the "what outcome, tracked how" layer.
def _goal_fields_for_domain(domain: str, persona: Persona) -> dict:
    return {
        "nutrition_hydration": {
            "baseline": "Appetite variable; sometimes leaves meals unfinished.",
            "target": "Consistently eat at least 75% of meals and meet the daily fluid target.",
            "measurement": "Percentage of meals eaten; daily fluid intake total.",
        },
        "mobility": {
            "baseline": f"Currently mobilises at '{persona.mobility_level.replace('_', ' ')}' level.",
            "target": "Maintain comfortable positioning and prevent contractures."
            if persona.mobility_level == "bed_bound"
            else "Maintain or improve current level of independence in mobilising.",
            "measurement": "Mobility level at reassessment; falls frequency.",
        },
        "continence": {
            "baseline": f"Uses {persona.continence_product.replace('_', ' ')} for continence support.",
            "target": "Maintain skin integrity and dignity; minimise incontinence-associated skin damage.",
            "measurement": "Continence event frequency; skin condition at each change.",
        },
        "communication": {
            "baseline": f"Primary communication method: {persona.communication_method.replace('_', ' ')}.",
            "target": "Maintain effective two-way communication with staff and family.",
            "measurement": "Frequency and quality of recorded communication interactions.",
        },
        "behaviour_wellbeing": {
            "baseline": "Some episodes of distress/agitation noted.",
            "target": "Reduce frequency and severity of distress episodes through consistent, person-centred approaches.",
            "measurement": "Number and severity of behaviour incidents; mood trend.",
        },
        "skin_integrity": {
            "baseline": f"Waterlow risk level: {persona.skin_risk_baseline}.",
            "target": "No new pressure damage; maintain intact skin.",
            "measurement": "Skin integrity assessment score; presence of new wounds.",
        },
        "medication": {
            "baseline": "Takes regular prescribed medication.",
            "target": "Safe administration of all medications, with prompt escalation of any refusal pattern.",
            "measurement": "Medication administration/refusal rate.",
        },
        "sleep": {
            "baseline": "Sleep pattern occasionally disrupted.",
            "target": "Improve sleep continuity and reduce night-time waking.",
            "measurement": "Number of night wakings; sleep quality rating.",
        },
        "pain_management": {
            "baseline": "Pain not always consistently recognised or reported.",
            "target": "Pain identified and managed promptly, including for non-verbal presentation.",
            "measurement": "Pain assessment scores; PRN analgesia effectiveness.",
        },
        "social_activities": {
            "baseline": "Engagement in group activities variable.",
            "target": "Increase meaningful participation in activities aligned with personal interests.",
            "measurement": "Activity participation rate and engagement level.",
        },
        "end_of_life": {
            "baseline": "Advance wishes discussed with resident/family.",
            "target": "Ensure comfort-focused, dignified care in line with recorded wishes.",
            "measurement": "Symptom control; adherence to recorded preferences.",
        },
    }[domain]


def _domains_for_persona(rng: random.Random, persona: Persona) -> list[str]:
    domains = ["nutrition_hydration", "mobility", "medication", "social_activities"]
    if persona.continence_product != "none":
        domains.append("continence")
    if persona.communication_method != "verbal" or persona.hearing_impairment or persona.visual_impairment:
        domains.append("communication")
    if persona.cognition != "intact":
        domains.append("behaviour_wellbeing")
    if persona.skin_risk_baseline in ("high", "very_high"):
        domains.append("skin_integrity")
    if rng.random() < 0.4:
        domains.append("sleep")
    if rng.random() < 0.3:
        domains.append("pain_management")
    if persona.dnacpr and rng.random() < 0.3:
        domains.append("end_of_life")
    return domains


def build_resident_row(
    persona: Persona, care_home_id: uuid.UUID, resident_id: uuid.UUID, rng: random.Random, floor_id: uuid.UUID | None = None
) -> dict:
    return {
        "id": resident_id,
        "care_home_id": care_home_id,
        "floor_id": floor_id,
        "first_name": persona.first_name,
        "last_name": persona.last_name,
        "preferred_name": persona.preferred_name,
        "date_of_birth": persona.date_of_birth,
        "nhs_number": f"{rng.randint(100, 999)} {rng.randint(100, 999)} {rng.randint(1000, 9999)}",
        "gender": persona.gender,
        "room_number": f"{rng.randint(1, 4)}{rng.choice('ABCDEFGH')}",
        "admission_date": persona.admission_date,
        "discharge_date": None,
        "status": "active",
        "gp_practice_name": rng.choice(["Riverside Surgery", "Elmwood Medical Centre", "St. Anne's Practice"]),
        "gp_phone": f"01{rng.randint(1000000, 9999999)}",
    }


def build_resident_setup(
    rng: random.Random,
    *,
    care_home_id: uuid.UUID,
    resident_id: uuid.UUID,
    persona: Persona,
    staff_user_ids: list[uuid.UUID],
    manager_user_id: uuid.UUID,
    window_start: date,
) -> tuple[dict[str, list[dict]], list[uuid.UUID]]:
    """Returns (rows keyed by table name, medication ids just created for this
    resident) -- callers need the medication ids to generate medication_events later.
    Includes 0-2 family `users` + `user_resident_links` rows too, since those only
    make sense alongside a specific resident."""
    recorded_by = lambda: rng.choice(staff_user_ids)  # noqa: E731

    rows: dict[str, list[dict]] = {
        "resident_contacts": _build_contacts(rng, care_home_id, resident_id),
        "resident_consents": _build_consents(rng, care_home_id, resident_id, manager_user_id),
        "resident_life_history": _build_life_history(rng, care_home_id, resident_id, persona, recorded_by()),
        "resident_preferences": _build_preferences(rng, care_home_id, resident_id, recorded_by),
        "resident_daily_routines": _build_daily_routines(rng, care_home_id, resident_id),
        "resident_allergies": _build_allergies(rng, care_home_id, resident_id, persona, recorded_by),
        "resident_diagnoses": _build_diagnoses(rng, care_home_id, resident_id, persona),
        "advance_care_directives": _build_advance_care_directives(rng, care_home_id, resident_id, persona, manager_user_id),
        "communication_needs": _build_communication_needs(rng, care_home_id, resident_id, persona, recorded_by()),
        "nutrition_hydration_targets": _build_nutrition_targets(rng, care_home_id, resident_id, persona, window_start, recorded_by()),
        "mobility_assessments": _build_mobility_assessment(rng, care_home_id, resident_id, persona, window_start, recorded_by()),
        "skin_integrity_assessments": _build_skin_assessment(rng, care_home_id, resident_id, persona, window_start, recorded_by()),
    }
    if persona.continence_product != "none":
        rows["continence_care_plans"] = _build_continence_care_plan(
            rng, care_home_id, resident_id, persona, window_start, recorded_by()
        )
    else:
        rows["continence_care_plans"] = []

    medications, medication_ids = _build_medications(rng, care_home_id, resident_id, persona, window_start)
    rows["medications"] = medications

    care_plans, care_plan_versions, care_plan_goals = _build_care_plans(rng, care_home_id, resident_id, persona, recorded_by)
    rows["care_plans"] = care_plans
    rows["care_plan_versions"] = care_plan_versions
    rows["care_plan_goals"] = care_plan_goals

    family_users, family_links = _build_family(rng, care_home_id, resident_id, persona, manager_user_id)
    rows["users"] = family_users
    rows["user_resident_links"] = family_links

    return rows, medication_ids


def _build_contacts(rng: random.Random, care_home_id: uuid.UUID, resident_id: uuid.UUID) -> list[dict]:
    n = rng.choices([1, 2], weights=[0.6, 0.4])[0]
    contacts = []
    for i in range(n):
        contacts.append(
            {
                "id": seeded_uuid(rng),
                "care_home_id": care_home_id,
                "resident_id": resident_id,
                "full_name": f"{rng.choice(['Susan', 'Peter', 'Karen', 'Ian', 'Linda', 'Paul'])} {rng.choice(['Baker', 'Whitfield', 'Nolan'])}",
                "relationship": random_family_relationship(rng),
                "is_next_of_kin": i == 0,
                "is_emergency_contact": i == 0,
                "has_poa_health": i == 0 and rng.random() < 0.3,
                "has_poa_finance": i == 0 and rng.random() < 0.3,
                "phone": f"07{rng.randint(100000000, 999999999)}",
                "email": f"contact{rng.randint(1000, 9999)}@example.test",
                "address": None,
                "notes": None,
            }
        )
    return contacts


def _build_consents(rng: random.Random, care_home_id: uuid.UUID, resident_id: uuid.UUID, manager_user_id: uuid.UUID) -> list[dict]:
    consent_types = ["data_processing", "family_digest_access", "photography", "ai_summarisation"]
    rows = []
    for consent_type in consent_types:
        capacity_assessed = rng.random() < 0.7
        status = rng.choices(["granted", "declined", "pending"], weights=[0.75, 0.15, 0.1])[0]
        rows.append(
            {
                "id": seeded_uuid(rng),
                "care_home_id": care_home_id,
                "resident_id": resident_id,
                "consent_type": consent_type,
                "status": status,
                "consented_by": "resident" if capacity_assessed else "best_interests_decision",
                "capacity_assessed": capacity_assessed,
                "best_interests_note": None if capacity_assessed else "Best interests decision made with family and MDT input.",
                "recorded_by": manager_user_id,
                "valid_from": date.today() - timedelta(days=rng.randint(30, 365)),
                "valid_to": None,
            }
        )
    return rows


def _build_life_history(rng: random.Random, care_home_id: uuid.UUID, resident_id: uuid.UUID, persona: Persona, recorded_by: uuid.UUID) -> list[dict]:
    occupation = rng.choice(OCCUPATIONS)
    hobbies = ", ".join(rng.sample(HOBBIES, k=rng.randint(1, 3)))
    faith = rng.choice(FAITHS)
    narrative = (
        f"{persona.preferred_name or persona.first_name} worked as a {occupation} before retiring. "
        f"Enjoys {hobbies}. "
        + ("Served in the armed forces. " if persona.is_veteran else "")
        + f"Describes themselves as {rng.choice(['a homebody', 'a people person', 'quietly independent', 'the life of the party in their day'])}."
    )
    return [
        {
            "id": seeded_uuid(rng),
            "care_home_id": care_home_id,
            "resident_id": resident_id,
            "occupation": occupation,
            "family_background": rng.choice(FAMILY_BACKGROUND_SNIPPETS),
            "significant_events": rng.choice(SIGNIFICANT_EVENTS_SNIPPETS),
            "hobbies_interests": hobbies,
            "important_relationships": rng.choice(IMPORTANT_RELATIONSHIPS_SNIPPETS),
            "faith_religion": faith,
            "cultural_background": rng.choice(CULTURAL_BACKGROUNDS),
            "language_preferred": "English",
            "military_veteran": persona.is_veteran,
            "free_text_narrative": narrative,
            "created_by": recorded_by,
        }
    ]


def _build_preferences(rng: random.Random, care_home_id: uuid.UUID, resident_id: uuid.UUID, recorded_by) -> list[dict]:
    rows = []
    for category, items in PREFERENCE_ITEMS.items():
        for preference, is_like in rng.sample(items, k=min(2, len(items))):
            rows.append(
                {
                    "id": seeded_uuid(rng),
                    "care_home_id": care_home_id,
                    "resident_id": resident_id,
                    "category": category,
                    "preference": preference,
                    "is_like": is_like,
                    "priority": rng.randint(1, 5),
                    "recorded_by": recorded_by(),
                }
            )
    return rows


def _build_daily_routines(rng: random.Random, care_home_id: uuid.UUID, resident_id: uuid.UUID) -> list[dict]:
    wake = time(rng.randint(6, 9), rng.choice([0, 15, 30, 45]))
    bed = time(rng.randint(19, 22), rng.choice([0, 15, 30, 45]))
    routines = [
        {"routine_type": "wake_time", "preferred_time": wake, "day_of_week": None, "notes": None},
        {"routine_type": "bed_time", "preferred_time": bed, "day_of_week": None, "notes": None},
        {
            "routine_type": "bathing_day",
            "preferred_time": time(10, 0),
            "day_of_week": rng.randint(0, 6),
            "notes": "Prefers a shower rather than a bath." if rng.random() < 0.5 else None,
        },
    ]
    return [
        {
            "id": seeded_uuid(rng),
            "care_home_id": care_home_id,
            "resident_id": resident_id,
            **routine,
        }
        for routine in routines
    ]


def _build_allergies(rng: random.Random, care_home_id: uuid.UUID, resident_id: uuid.UUID, persona: Persona, recorded_by) -> list[dict]:
    if persona.n_allergies == 0:
        return []
    chosen = rng.sample(ALLERGENS, k=min(persona.n_allergies, len(ALLERGENS)))
    return [
        {
            "id": seeded_uuid(rng),
            "care_home_id": care_home_id,
            "resident_id": resident_id,
            "allergen": allergen,
            "reaction": reaction,
            "severity": severity,
            "verified_by": recorded_by(),
        }
        for allergen, reaction, severity in chosen
    ]


def _build_diagnoses(rng: random.Random, care_home_id: uuid.UUID, resident_id: uuid.UUID, persona: Persona) -> list[dict]:
    chosen = rng.sample(DIAGNOSES, k=min(persona.n_diagnoses, len(DIAGNOSES)))
    rows = []
    for i, (condition_name, icd10_code) in enumerate(chosen):
        rows.append(
            {
                "id": seeded_uuid(rng),
                "care_home_id": care_home_id,
                "resident_id": resident_id,
                "condition_name": condition_name,
                "icd10_code": icd10_code,
                "diagnosed_date": persona.admission_date - timedelta(days=rng.randint(30, 3000)),
                "is_primary": i == 0,
                "status": "active",
                "notes": None,
            }
        )
    return rows


_DIRECTIVE_SUMMARIES = {
    "DNACPR": "Do Not Attempt Cardiopulmonary Resuscitation, agreed with resident/family and GP.",
    "ReSPECT": "Recommended Summary Plan for Emergency Care and Treatment, covering realistic treatment "
    "options and ceiling of care in an emergency, agreed with resident/family and clinician.",
    "advance_decision": "Advance Decision to Refuse Treatment (ADRT), specifying treatments the resident "
    "does not wish to receive in specified future circumstances.",
    "ceiling_of_care": "Agreed ceiling of care: treatment appropriate to comfort and dignity, without "
    "escalation to invasive intervention or hospital admission except for symptom relief.",
}


def _build_advance_care_directives(
    rng: random.Random, care_home_id: uuid.UUID, resident_id: uuid.UUID, persona: Persona, manager_user_id: uuid.UUID
) -> list[dict]:
    directive_types = []
    if persona.dnacpr:
        directive_types.append("DNACPR")
        if rng.random() < 0.5:
            directive_types.append("ReSPECT")
        if rng.random() < 0.15:
            directive_types.append("ceiling_of_care")
    elif persona.mobility_level in ("hoist_dependent", "bed_bound") and rng.random() < 0.3:
        directive_types.append("ReSPECT")
    if rng.random() < 0.1 and "advance_decision" not in directive_types:
        directive_types.append("advance_decision")

    return [
        {
            "id": seeded_uuid(rng),
            "care_home_id": care_home_id,
            "resident_id": resident_id,
            "directive_type": directive_type,
            "summary": _DIRECTIVE_SUMMARIES[directive_type],
            "document_reference": f"{directive_type.upper()}-{rng.randint(1000, 9999)}",
            "signed_by_clinician": "Dr. " + rng.choice(["Patel", "Osei", "Nowak", "Hughes"]),
            "review_due": date.today() + timedelta(days=180),
            "is_current": True,
        }
        for directive_type in directive_types
    ]


def _build_communication_needs(
    rng: random.Random, care_home_id: uuid.UUID, resident_id: uuid.UUID, persona: Persona, recorded_by: uuid.UUID
) -> list[dict]:
    return [
        {
            "id": seeded_uuid(rng),
            "care_home_id": care_home_id,
            "resident_id": resident_id,
            "primary_method": persona.communication_method,
            "hearing_impairment": persona.hearing_impairment,
            "hearing_aid_used": persona.hearing_impairment,
            "visual_impairment": persona.visual_impairment,
            "glasses_used": persona.visual_impairment,
            "cognitive_considerations": (
                "Responds best to short, simple sentences and visual prompts." if persona.cognition == "advanced_dementia" else None
            ),
            "interpreter_language": None,
            "aac_tools": "Picture cards" if persona.communication_method == "picture_cards" else None,
            "notes": None,
            "recorded_by": recorded_by,
        }
    ]


def _build_continence_care_plan(
    rng: random.Random, care_home_id: uuid.UUID, resident_id: uuid.UUID, persona: Persona, window_start: date, recorded_by: uuid.UUID
) -> list[dict]:
    return [
        {
            "id": seeded_uuid(rng),
            "care_home_id": care_home_id,
            "resident_id": resident_id,
            "toileting_schedule": rng.choice(["Prompted every 2 hours", "Prompted every 3 hours", "On request"]),
            "product_regime": persona.continence_product,
            "bowel_management_plan": None,
            "set_by": recorded_by,
            "effective_from": window_start,
        }
    ]


def _build_nutrition_targets(
    rng: random.Random, care_home_id: uuid.UUID, resident_id: uuid.UUID, persona: Persona, window_start: date, recorded_by: uuid.UUID
) -> list[dict]:
    return [
        {
            "id": seeded_uuid(rng),
            "care_home_id": care_home_id,
            "resident_id": resident_id,
            "daily_fluid_target_ml": persona.fluid_baseline_ml,
            "daily_calorie_target": rng.randint(1600, 2200),
            "set_by": recorded_by,
            "effective_from": window_start,
            "effective_to": None,
        }
    ]


def _build_mobility_assessment(
    rng: random.Random, care_home_id: uuid.UUID, resident_id: uuid.UUID, persona: Persona, window_start: date, recorded_by: uuid.UUID
) -> list[dict]:
    aids = {
        "independent": [],
        "requires_supervision": ["walking_stick"],
        "requires_one_assist": ["zimmer_frame"],
        "requires_two_assist": ["zimmer_frame", "wheelchair"],
        "hoist_dependent": ["wheelchair", "hoist"],
        "bed_bound": ["hoist"],
    }[persona.mobility_level]
    risk_level = {0: "low", 1: "low", 2: "medium", 3: "medium", 4: "high", 5: "very_high"}[
        min(persona.falls_risk_baseline // 5, 5)
    ]
    return [
        {
            "id": seeded_uuid(rng),
            "care_home_id": care_home_id,
            "resident_id": resident_id,
            "mobility_level": persona.mobility_level,
            "aids_used": aids,
            "transfer_method": "Standing hoist" if "hoist" in aids else None,
            "falls_risk_score": persona.falls_risk_baseline,
            "falls_risk_level": risk_level,
            "assessed_by": recorded_by,
            "assessed_at": datetime.combine(window_start, time(9, 0), tzinfo=UTC),
            "next_review_due": window_start + timedelta(days=90),
            "notes": None,
        }
    ]


def _build_skin_assessment(
    rng: random.Random, care_home_id: uuid.UUID, resident_id: uuid.UUID, persona: Persona, window_start: date, recorded_by: uuid.UUID
) -> list[dict]:
    score_by_level = {"low": rng.randint(5, 9), "medium": rng.randint(10, 14), "high": rng.randint(15, 19), "very_high": rng.randint(20, 25)}
    areas = ["sacrum", "heels"] if persona.mobility_level in ("hoist_dependent", "bed_bound") else ["heels"]
    return [
        {
            "id": seeded_uuid(rng),
            "care_home_id": care_home_id,
            "resident_id": resident_id,
            "assessment_tool": "Waterlow",
            "total_score": score_by_level[persona.skin_risk_baseline],
            "risk_level": persona.skin_risk_baseline,
            "pressure_areas_checked": areas,
            "equipment_in_use": "Pressure-relieving mattress" if persona.skin_risk_baseline in ("high", "very_high") else None,
            "reposition_frequency": "Every 2 hours" if persona.skin_risk_baseline in ("high", "very_high") else None,
            "assessed_by": recorded_by,
            "assessed_at": datetime.combine(window_start, time(9, 30), tzinfo=UTC),
            "next_review_due": window_start + timedelta(days=30),
        }
    ]


def _build_medications(
    rng: random.Random, care_home_id: uuid.UUID, resident_id: uuid.UUID, persona: Persona, window_start: date
) -> tuple[list[dict], list[uuid.UUID]]:
    n_regular = rng.randint(2, 6)
    chosen_regular = rng.sample(REGULAR_MEDICATIONS, k=min(n_regular, len(REGULAR_MEDICATIONS)))
    n_prn = rng.randint(0, 2)
    chosen_prn = rng.sample(PRN_MEDICATIONS, k=min(n_prn, len(PRN_MEDICATIONS)))

    rows = []
    ids = []
    for drug_name, dose, route in chosen_regular:
        med_id = seeded_uuid(rng)
        ids.append(med_id)
        n_times = rng.choice([1, 2, 3])
        schedule_times = sorted(rng.sample([time(8, 0), time(12, 0), time(18, 0), time(20, 0)], k=n_times))
        rows.append(
            {
                "id": med_id,
                "care_home_id": care_home_id,
                "resident_id": resident_id,
                "drug_name": drug_name,
                "dose": dose,
                "route": route,
                "schedule_times": schedule_times,
                "is_prn": False,
                "prn_max_per_day": None,
                "prn_indication": None,
                "prescriber": "Dr. " + rng.choice(["Patel", "Osei", "Nowak", "Hughes"]),
                "start_date": persona.admission_date,
                "end_date": None,
                "stock_count": rng.randint(10, 60),
                "stock_reorder_threshold": 7,
                "is_active": True,
            }
        )
    for drug_name, dose, route, indication in chosen_prn:
        med_id = seeded_uuid(rng)
        ids.append(med_id)
        rows.append(
            {
                "id": med_id,
                "care_home_id": care_home_id,
                "resident_id": resident_id,
                "drug_name": drug_name,
                "dose": dose,
                "route": route,
                "schedule_times": [],
                "is_prn": True,
                "prn_max_per_day": rng.choice([2, 4]),
                "prn_indication": indication,
                "prescriber": "Dr. " + rng.choice(["Patel", "Osei", "Nowak", "Hughes"]),
                "start_date": persona.admission_date,
                "end_date": None,
                "stock_count": rng.randint(10, 30),
                "stock_reorder_threshold": 5,
                "is_active": True,
            }
        )
    return rows, ids


def _build_care_plans(
    rng: random.Random, care_home_id: uuid.UUID, resident_id: uuid.UUID, persona: Persona, recorded_by
) -> tuple[list[dict], list[dict], list[dict]]:
    domains = _domains_for_persona(rng, persona)
    plans = []
    versions = []
    goals = []
    for domain in domains:
        plan_id = seeded_uuid(rng)
        set_by = recorded_by()
        plans.append(
            {
                "id": plan_id,
                "care_home_id": care_home_id,
                "resident_id": resident_id,
                "domain": domain,
                "goal": _CARE_PLAN_GOALS[domain],
                "current_version": 1,
                "review_due": date.today() + timedelta(days=90),
                "is_active": True,
            }
        )
        versions.append(
            {
                "id": seeded_uuid(rng),
                "care_home_id": care_home_id,
                "care_plan_id": plan_id,
                "version_number": 1,
                "content": _CARE_PLAN_GOALS[domain],
                "changed_by": set_by,
                "change_reason": "Initial care plan on admission.",
            }
        )
        goal_fields = _goal_fields_for_domain(domain, persona)
        goals.append(
            {
                "id": seeded_uuid(rng),
                "care_home_id": care_home_id,
                "resident_id": resident_id,
                "care_plan_id": plan_id,
                "goal_text": _CARE_PLAN_GOALS[domain],
                "baseline": goal_fields["baseline"],
                "target": goal_fields["target"],
                "measurement": goal_fields["measurement"],
                "status": "in_progress",
                "set_by": set_by,
                "review_date": date.today() + timedelta(days=90),
                "achieved_date": None,
            }
        )

    # ~40% of residents also get a 'personal' aspiration plan/goal -- future-facing,
    # person-centred, deliberately not one of the 11 clinical domains (migration
    # 0020's care_plan_domain 'personal' value).
    if rng.random() < 0.4:
        aspiration = rng.choice(PERSONAL_ASPIRATIONS)
        goal_text = f"I would like to {aspiration}."
        plan_id = seeded_uuid(rng)
        set_by = recorded_by()
        plans.append(
            {
                "id": plan_id,
                "care_home_id": care_home_id,
                "resident_id": resident_id,
                "domain": "personal",
                "goal": goal_text,
                "current_version": 1,
                "review_due": date.today() + timedelta(days=90),
                "is_active": True,
            }
        )
        versions.append(
            {
                "id": seeded_uuid(rng),
                "care_home_id": care_home_id,
                "care_plan_id": plan_id,
                "version_number": 1,
                "content": goal_text,
                "changed_by": set_by,
                "change_reason": "Recorded during person-centred planning discussion.",
            }
        )
        goals.append(
            {
                "id": seeded_uuid(rng),
                "care_home_id": care_home_id,
                "resident_id": resident_id,
                "care_plan_id": plan_id,
                "goal_text": goal_text,
                "baseline": "Not currently doing this as often as they'd like.",
                "target": f"Support {aspiration} on a regular, sustainable basis.",
                "measurement": "Frequency of supported opportunities; resident-reported satisfaction.",
                "status": "in_progress",
                "set_by": set_by,
                "review_date": date.today() + timedelta(days=90),
                "achieved_date": None,
            }
        )

    return plans, versions, goals


def _build_family(
    rng: random.Random, care_home_id: uuid.UUID, resident_id: uuid.UUID, persona: Persona, manager_user_id: uuid.UUID
) -> tuple[list[dict], list[dict]]:
    n_family = rng.choices([0, 1, 2], weights=[0.1, 0.7, 0.2])[0]
    users = []
    links = []
    for i in range(n_family):
        user = build_family_user(rng, care_home_id, persona.last_name, suffix=f"{resident_id.hex[:6]}{i}")
        users.append(user)
        links.append(
            {
                "id": seeded_uuid(rng),
                "care_home_id": care_home_id,
                "user_id": user["id"],
                "resident_id": resident_id,
                "relationship": random_family_relationship(rng),
                "granted_by": manager_user_id,
                "granted_at": datetime.now(UTC),
                "revoked_at": None,
            }
        )
    return users, links
