"""Clinical safety starts at input validation -- implausible values are flagged, not
rejected. See app/modules/observations/schemas.py."""

from app.modules.observations.models import ObservationType
from app.modules.observations.schemas import is_plausible


def test_fluid_within_bounds_is_plausible():
    assert is_plausible(ObservationType.FLUID_INTAKE, {"ml": 250}) is True


def test_fluid_above_bound_is_flagged():
    assert is_plausible(ObservationType.FLUID_INTAKE, {"ml": 5000}) is False


def test_weight_within_bounds_is_plausible():
    assert is_plausible(ObservationType.WEIGHT, {"kg": 70}) is True


def test_weight_below_bound_is_flagged():
    assert is_plausible(ObservationType.WEIGHT, {"kg": 2}) is False


def test_missing_field_is_not_flagged():
    # No bound to check against -> plausible by default, never a false positive on
    # partial data.
    assert is_plausible(ObservationType.VITALS, {}) is True


def test_unbounded_type_is_always_plausible():
    assert is_plausible(ObservationType.MEAL, {"meal": "lunch", "fraction_eaten": 1.4}) is True
