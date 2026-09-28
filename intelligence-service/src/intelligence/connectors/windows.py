"""Calendar windows for the observation API's date-normalized projection."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from intelligence.core.contracts import Period


def observation_fetch_period(shift: Period, *, care_home_timezone: str) -> Period:
    """Expand a bounded handover shift to its overlapping local calendar days.

    This is a fetch window only. Keep the original shift for evidence assembly.
    The existing Period maximum duration still applies to the expanded window.
    """
    zone = ZoneInfo(care_home_timezone)
    start = shift.start.astimezone(UTC)
    end = shift.end.astimezone(UTC)
    if start >= end:
        raise ValueError("Shift start must precede shift end")
    first_date = start.astimezone(zone).date()
    last_date = (end - timedelta(microseconds=1)).astimezone(zone).date()
    return Period(
        start=datetime.combine(first_date, time.min, tzinfo=zone),
        end=datetime.combine(last_date + timedelta(days=1), time.min, tzinfo=zone),
    )
