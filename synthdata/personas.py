"""Persona = the parameters that make one synthetic resident's data look like a real
person's rather than uniform noise, across every clinical domain the real schema
covers -- not just appetite/fluids. Correlated fields (e.g. bed-bound residents skew
toward higher skin-integrity risk and full continence support) are derived here once,
then read by setup_records.py and daily_records.py so the whole dataset stays
internally consistent for one resident.
"""

import dataclasses
import random
from datetime import date, timedelta

from synthdata.reference_data import RESIDENT_FIRST_NAMES, RESIDENT_LAST_NAMES

MOBILITY_LEVELS = [
    "independent", "requires_supervision", "requires_one_assist",
    "requires_two_assist", "hoist_dependent", "bed_bound",
]
COGNITION_LEVELS = ["intact", "mild_impairment", "advanced_dementia"]
COMMUNICATION_METHODS = ["verbal", "non_verbal", "sign", "picture_cards", "assistive_device", "written"]
CONTINENCE_PRODUCTS = ["none", "pad", "pull_up", "pad_and_pants", "catheter"]
SKIN_RISK_LEVELS = ["low", "medium", "high", "very_high"]


@dataclasses.dataclass(frozen=True)
class Persona:
    first_name: str
    last_name: str
    preferred_name: str | None
    gender: str
    date_of_birth: date
    admission_date: date

    mobility_level: str
    cognition: str
    appetite_baseline: float          # 0..1, fraction of a meal typically finished
    fluid_baseline_ml: int            # typical total daily fluid intake
    refusal_rate: float               # 0..1, probability of refusing a given care task
    weight_kg: float
    height_cm: float

    continence_product: str
    communication_method: str
    hearing_impairment: bool
    visual_impairment: bool
    dysphagia: bool                   # drives texture-modified diet / thickened fluids

    skin_risk_baseline: str
    falls_risk_baseline: int          # 0..30-ish, higher = more likely to fall
    dnacpr: bool
    is_veteran: bool

    n_diagnoses: int
    n_allergies: int


def _weighted(rng: random.Random, options: list[str], weights: list[float]) -> str:
    return rng.choices(options, weights=weights)[0]


def generate_persona(rng: random.Random, *, window_start: date) -> Persona:
    cognition = _weighted(rng, COGNITION_LEVELS, [0.4, 0.35, 0.25])
    mobility_level = _weighted(
        rng, MOBILITY_LEVELS, [0.2, 0.2, 0.25, 0.15, 0.1, 0.1]
    )

    # Correlated risk: reduced mobility -> higher skin-integrity risk baseline.
    mobility_risk_index = MOBILITY_LEVELS.index(mobility_level)
    skin_risk_weights = [
        max(0.05, 0.4 - 0.07 * mobility_risk_index),
        0.35,
        0.15 + 0.05 * mobility_risk_index,
        0.05 + 0.05 * mobility_risk_index,
    ]
    skin_risk_baseline = _weighted(rng, SKIN_RISK_LEVELS, skin_risk_weights)

    # Continence need correlates with both mobility and cognition.
    if mobility_level in ("hoist_dependent", "bed_bound") or cognition == "advanced_dementia":
        continence_product = _weighted(rng, CONTINENCE_PRODUCTS, [0.02, 0.28, 0.2, 0.4, 0.1])
    else:
        continence_product = _weighted(rng, CONTINENCE_PRODUCTS, [0.55, 0.3, 0.1, 0.04, 0.01])

    communication_method = (
        "verbal" if cognition != "advanced_dementia" else _weighted(rng, COMMUNICATION_METHODS, [0.3, 0.35, 0.05, 0.15, 0.1, 0.05])
    )

    dob = date(rng.randint(1925, 1945), rng.randint(1, 12), rng.randint(1, 28))
    admission_date = window_start - timedelta(days=rng.randint(60, 365 * 4))

    return Persona(
        first_name=rng.choice(RESIDENT_FIRST_NAMES),
        last_name=rng.choice(RESIDENT_LAST_NAMES),
        preferred_name=None if rng.random() < 0.7 else rng.choice(["Peggy", "Art", "Dot", "Frankie", "Bill", "Vee"]),
        gender=rng.choice(["female", "male"]),
        date_of_birth=dob,
        admission_date=admission_date,
        mobility_level=mobility_level,
        cognition=cognition,
        appetite_baseline=rng.uniform(0.5, 0.95),
        fluid_baseline_ml=rng.randint(1200, 2000),
        refusal_rate=rng.uniform(0.0, 0.15) if cognition == "intact" else rng.uniform(0.05, 0.3),
        weight_kg=rng.uniform(48, 95),
        height_cm=rng.uniform(150, 182),
        continence_product=continence_product,
        communication_method=communication_method,
        hearing_impairment=rng.random() < 0.35,
        visual_impairment=rng.random() < 0.25,
        dysphagia=rng.random() < (0.3 if cognition == "advanced_dementia" else 0.1),
        skin_risk_baseline=skin_risk_baseline,
        falls_risk_baseline=int(5 + mobility_risk_index * 4 + rng.uniform(-2, 4)),
        dnacpr=rng.random() < (0.55 if mobility_level == "bed_bound" else 0.25),
        is_veteran=rng.random() < 0.08,
        n_diagnoses=rng.randint(1, 4),
        n_allergies=rng.choices([0, 1, 2], weights=[0.55, 0.35, 0.1])[0],
    )
