"""Calendar shift boundaries shared by manual and scheduled submission."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from intelligence.core.contracts import Period


def completed_shifts(*, now: datetime, timezone: str, count: int = 4) -> tuple[Period, ...]:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if not 1 <= count <= 14:
        raise ValueError("count must be between 1 and 14")
    zone = ZoneInfo(timezone)
    local = now.astimezone(zone)
    boundaries = sorted(
        datetime.combine(local.date() - timedelta(days=day), time(hour), zone)
        for day in range(count // 2 + 3)
        for hour in (7, 19)
    )
    boundaries = [boundary for boundary in boundaries if boundary <= local]
    return tuple(
        Period(start=start.astimezone(UTC), end=end.astimezone(UTC))
        for start, end in reversed(list(zip(boundaries[:-1], boundaries[1:], strict=True)))
    )[:count]
