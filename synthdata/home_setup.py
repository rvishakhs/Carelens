"""Home-level setup: the single care_homes row, staff + family user accounts, and the
activity calendar -- concrete scheduled occurrences spread across the whole window
(not just activity *types*), which daily_records.py assigns resident participation
against.
"""

import random
import uuid
from datetime import UTC, date, datetime, time, timedelta

from synthdata.ids import seeded_uuid
from synthdata.reference_data import FAMILY_RELATIONSHIPS, STAFF_FIRST_NAMES, STAFF_LAST_NAMES

STAFF_ROLE_WEIGHTS = {"carer": 0.55, "nurse": 0.25, "manager": 0.15, "system_admin": 0.05}

# weekday (Monday=0, per date.weekday()) -> [(name, category, time), ...]
_WEEKLY_ACTIVITY_SCHEDULE: dict[int, list[tuple[str, str, time]]] = {
    0: [("Armchair exercise", "physical", time(10, 0)), ("Bingo", "social", time(14, 0))],
    1: [("Garden club", "physical", time(10, 0)), ("Reminiscence group", "cognitive", time(14, 0))],
    2: [("Arts and crafts", "creative", time(10, 0)), ("Music and memories", "cognitive", time(14, 0))],
    3: [("Armchair exercise", "physical", time(10, 0)), ("Bingo", "social", time(14, 0))],
    4: [("Movie afternoon", "social", time(14, 0))],
    5: [("Garden club", "physical", time(10, 30))],
    6: [("Sunday service", "spiritual", time(11, 0))],
}


def build_care_home(rng: random.Random, name: str) -> dict:
    return {
        "id": seeded_uuid(rng),
        "name": name,
        "cqc_location_id": f"1-{rng.randint(100000000, 999999999)}",
        "address_line1": f"{rng.randint(1, 200)} {rng.choice(['Elm', 'Oak', 'Station', 'Church', 'Mill'])} Road",
        "city": rng.choice(["Manchester", "Leeds", "Bristol", "Nottingham", "Coventry"]),
        "postcode": (
            f"{rng.choice(['M', 'LS', 'BS', 'NG', 'CV'])}{rng.randint(1, 20)} "
            f"{rng.randint(1, 9)}{rng.choice('ABCDEFGH')}{rng.choice('ABCDEFGH')}"
        ),
        "phone": f"0{rng.randint(1000000000, 9999999999)}"[:11],
        "timezone": "Europe/London",
    }


def build_floors(rng: random.Random, care_home_id: uuid.UUID) -> list[dict]:
    """Every synthetic care home gets exactly two floors -- enough to exercise
    floor-scoped RLS (migration 0013) without residents.floor_id staying NULL, which
    is what made every prior run's residents invisible under floor-scoped policies."""
    return [
        {
            "id": seeded_uuid(rng),
            "care_home_id": care_home_id,
            "name": "Ground Floor",
            "floor_type": "residential",
            "description": "General residential care.",
            "is_active": True,
        },
        {
            "id": seeded_uuid(rng),
            "care_home_id": care_home_id,
            "name": "First Floor",
            "floor_type": "dementia",
            "description": "Dementia-specialist care.",
            "is_active": True,
        },
    ]


def build_user_floor_links(rng: random.Random, care_home_id: uuid.UUID, staff_users: list[dict], floors: list[dict], granted_by: uuid.UUID) -> list[dict]:
    """Every staff member is granted every floor -- a single synthetic care home has
    no reason to restrict staff to one floor, and this is authorisation (which floors
    a user may EVER see), not the session-level floor selection RLS actually filters
    on (see migration 0013's docstring)."""
    return [
        {
            "id": seeded_uuid(rng),
            "care_home_id": care_home_id,
            "user_id": staff["id"],
            "floor_id": floor["id"],
            "granted_by": granted_by,
        }
        for staff in staff_users
        for floor in floors
    ]


def build_staff_users(rng: random.Random, care_home_id: uuid.UUID, count: int) -> list[dict]:
    roles = list(STAFF_ROLE_WEIGHTS.keys())
    weights = list(STAFF_ROLE_WEIGHTS.values())
    # Guarantee at least one manager and one nurse regardless of the random draw --
    # every care home has both, and downstream code (medication witnessing, review
    # sign-off) assumes at least one of each exists.
    forced_roles = ["manager", "nurse", *rng.choices(roles, weights=weights, k=max(count - 2, 1))]

    users = []
    for i, role in enumerate(forced_roles[:count]):
        first = rng.choice(STAFF_FIRST_NAMES)
        last = rng.choice(STAFF_LAST_NAMES)
        users.append(
            {
                "id": seeded_uuid(rng),
                "care_home_id": care_home_id,
                "oidc_subject": None,
                "email": f"{first.lower()}.{last.lower()}{i}@example-carehome.test",
                "display_name": f"{first} {last}",
                "role": role,
                "mfa_enrolled": role in ("manager", "system_admin") or rng.random() < 0.6,
                "is_active": True,
            }
        )
    return users


def build_admin_user(rng: random.Random, care_home_id: uuid.UUID, email: str) -> dict:
    """The one staff row every synthetic care home gets that's actually sign-in-able:
    generator.py provisions a real Keycloak account for it and fills in oidc_subject
    before this is inserted, unlike build_staff_users' rows (local-only, no login)."""
    first = rng.choice(STAFF_FIRST_NAMES)
    last = rng.choice(STAFF_LAST_NAMES)
    return {
        "id": seeded_uuid(rng),
        "care_home_id": care_home_id,
        "oidc_subject": None,
        "email": email,
        "display_name": f"{first} {last}",
        "role": "admin",
        "mfa_enrolled": True,
        "is_active": True,
    }


def build_family_user(rng: random.Random, care_home_id: uuid.UUID, resident_last_name: str, suffix: str) -> dict:
    first = rng.choice(STAFF_FIRST_NAMES)  # reuse a generic modern first-name pool for family members
    return {
        "id": seeded_uuid(rng),
        "care_home_id": care_home_id,
        "oidc_subject": None,
        "email": f"{first.lower()}.{resident_last_name.lower()}.{suffix}@example-family.test",
        "display_name": f"{first} {resident_last_name}",
        "role": "family",
        "mfa_enrolled": False,
        "is_active": True,
    }


def random_family_relationship(rng: random.Random) -> str:
    return rng.choice(FAMILY_RELATIONSHIPS)


def build_activity_occurrences(rng: random.Random, care_home_id: uuid.UUID, window_start: date, days: int) -> list[dict]:
    occurrences = []
    for day_index in range(days):
        day = window_start + timedelta(days=day_index)
        for name, category, activity_time in _WEEKLY_ACTIVITY_SCHEDULE.get(day.weekday(), []):
            occurrences.append(
                {
                    "id": seeded_uuid(rng),
                    "care_home_id": care_home_id,
                    "name": name,
                    "category": category,
                    "scheduled_at": datetime.combine(day, activity_time, tzinfo=UTC),
                    "location": "Garden room" if category == "physical" else "Main lounge",
                }
            )
    return occurrences
