from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from intelligence.core.errors import InvalidShift

from .contracts import HandoverSubmissionRequest

DAY_START = time(7)
DAY_END = time(19)


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def validate_completed_shift(
    request: HandoverSubmissionRequest,
    *,
    care_home_timezone: str,
    now: datetime,
) -> None:
    """Validate a completed 07:00–19:00 or 19:00–07:00 shift in the care home's timezone.

    Raises InvalidShift for client-correctable problems. A naive `now` is a
    programming error (server-supplied), so it raises ValueError instead.
    """
    if not _is_aware(now):
        raise ValueError("now must be timezone-aware")

    if not (_is_aware(request.shift_start) and _is_aware(request.shift_end)):
        raise InvalidShift("Shift start and end must include a timezone")

    zone = ZoneInfo(care_home_timezone)
    start = request.shift_start.astimezone(zone)
    end = request.shift_end.astimezone(zone)

    is_day_shift = (
        start.time() == DAY_START
        and end.time() == DAY_END
        and end.date() == start.date()
    )
    is_night_shift = (
        start.time() == DAY_END
        and end.time() == DAY_START
        and end.date() == start.date() + timedelta(days=1)
    )

    if not (is_day_shift or is_night_shift):
        raise InvalidShift(
            "Shift must be 07:00–19:00 or 19:00–07:00 in the care home's timezone"
        )

    if request.shift_end.astimezone(UTC) > now.astimezone(UTC):
        raise InvalidShift("The shift must have finished before submission")