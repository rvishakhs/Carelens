from datetime import UTC, datetime
from zoneinfo import ZoneInfoNotFoundError

import pytest

from intelligence.connectors.windows import observation_fetch_period
from intelligence.core.contracts import Period


@pytest.mark.parametrize(
    "start,end,expected_start,expected_end,hours",
    [
        (
            "2026-09-08T07:00:00+01:00",
            "2026-09-08T19:00:00+01:00",
            "2026-09-08T00:00:00+01:00",
            "2026-09-09T00:00:00+01:00",
            24,
        ),
        (
            "2026-09-08T19:00:00+01:00",
            "2026-09-09T07:00:00+01:00",
            "2026-09-08T00:00:00+01:00",
            "2026-09-10T00:00:00+01:00",
            48,
        ),
        (
            "2026-09-08T19:00:00+01:00",
            "2026-09-09T00:00:00+01:00",
            "2026-09-08T00:00:00+01:00",
            "2026-09-09T00:00:00+01:00",
            24,
        ),
        (
            "2026-10-24T19:00:00+01:00",
            "2026-10-25T07:00:00+00:00",
            "2026-10-24T00:00:00+01:00",
            "2026-10-26T00:00:00+00:00",
            49,
        ),
        (
            "2026-03-28T19:00:00+00:00",
            "2026-03-29T07:00:00+01:00",
            "2026-03-28T00:00:00+00:00",
            "2026-03-30T00:00:00+01:00",
            47,
        ),
        (
            "2026-09-08T06:00:00Z",
            "2026-09-08T18:00:00Z",
            "2026-09-08T00:00:00+01:00",
            "2026-09-09T00:00:00+01:00",
            24,
        ),
    ],
)
def test_calendar_windows(start, end, expected_start, expected_end, hours):
    shift = Period(start=start, end=end)
    result = observation_fetch_period(shift, care_home_timezone="Europe/London")
    assert result.start.isoformat() == expected_start
    assert result.end.isoformat() == expected_end
    assert (result.end.astimezone(UTC) - result.start.astimezone(UTC)).total_seconds() == hours * 3600
    assert shift.start == datetime.fromisoformat(start)
    assert shift.end == datetime.fromisoformat(end)


def test_invalid_timezone():
    with pytest.raises(ZoneInfoNotFoundError):
        observation_fetch_period(
            Period(start="2026-09-08T07:00:00Z", end="2026-09-08T19:00:00Z"),
            care_home_timezone="Invalid/Timezone",
        )
