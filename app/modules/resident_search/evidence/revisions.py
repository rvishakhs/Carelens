"""Canonical opaque revision tokens shared by citations and freshness checks."""

from datetime import UTC, datetime


def revision_token(value: datetime | str | None) -> str | None:
    if isinstance(value, datetime):
        if value.utcoffset() is None:
            raise ValueError("source revision timestamps must be timezone-aware")
        return value.astimezone(UTC).isoformat(timespec="microseconds")
    return value
