from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .contracts import HandoverSubmissionRequest


def validate_completed_shift(
    request: HandoverSubmissionRequest,
    *,
    care_home_timezone: str,
    now: datetime,
) -> None:
    """Validate a completed shift using trusted care-home configuration."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    zone = ZoneInfo(care_home_timezone)

    start = request.shift_start.astimezone(zone)
    end = request.shift_end.astimezone(zone)

    is_day_shift = (
        start.time() == time(7)
        and end.time() == time(19)
        and end.date() == start.date()
    )

    is_night_shift = (
        start.time() == time(19)
        and end.time() == time(7)
        and end.date() == start.date() + timedelta(days=1)
    )

    if not (is_day_shift or is_night_shift):
        raise ValueError(
            "Shift must be 07:00–19:00 or 19:00–07:00 "
            "in the care home's timezone"
        )

    if request.shift_end.astimezone(UTC) > now.astimezone(UTC):
        raise ValueError("The shift must have finished before submission")