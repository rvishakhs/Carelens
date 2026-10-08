from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from intelligence.handover.shifts import completed_shifts


@pytest.mark.parametrize(
    "now,end",
    [
        ("2026-10-08T05:59:59+00:00", "2026-10-07T18:00:00+00:00"),
        ("2026-10-08T06:00:00+00:00", "2026-10-08T06:00:00+00:00"),
        ("2026-10-08T18:00:00+00:00", "2026-10-08T18:00:00+00:00"),
    ],
)
def test_only_completed_shifts(now, end):
    shifts = completed_shifts(now=datetime.fromisoformat(now), timezone="Europe/London")
    assert shifts[0].end == datetime.fromisoformat(end)
    assert len(shifts) == 4
    assert all(first.start == second.end for first, second in zip(shifts, shifts[1:], strict=False))


@pytest.mark.parametrize("day,hours", [("2026-03-29", 11), ("2026-10-25", 13)])
def test_dst_nights_use_calendar_boundaries(day, hours):
    now = datetime.fromisoformat(day + "T07:00:00").replace(tzinfo=ZoneInfo("Europe/London"))
    shift = completed_shifts(now=now, timezone="Europe/London", count=1)[0]
    assert (shift.end - shift.start).total_seconds() == hours * 3600
    assert shift.start.astimezone(ZoneInfo("Europe/London")).hour == 19
    assert shift.end.astimezone(ZoneInfo("Europe/London")).hour == 7


def test_invalid_clock_and_count():
    with pytest.raises(ValueError):
        completed_shifts(now=datetime(2026, 1, 1), timezone="Europe/London")
    with pytest.raises(ValueError):
        completed_shifts(now=datetime(2026, 1, 1, tzinfo=UTC), timezone="Europe/London", count=15)
