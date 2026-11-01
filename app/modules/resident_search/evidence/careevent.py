import hashlib
import json
import uuid
from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.resident_search.evidence.models import AuthorityLevel, EvidenceDocument, EvidenceSourceType
from app.modules.resident_search.evidence.utils import _clean, _measurement_value, _topics_for_event

_PARENT_EVENT_BASE_SQL = """
SELECT
    e.id,
    e.resident_id,
    e.care_home_id,
    e.floor_id,
    e.occurred_at,
    e.updated_at,
    e.deleted_at,
    e.status,
    e.summary,
    e.note,
    t.id AS template_id,
    t.name AS template_name,
    c.id AS category_id,
    c.name AS category_name
FROM care_events e
JOIN care_templates t
    ON t.id = e.template_id
JOIN care_categories c
    ON c.id = e.category_id
JOIN residents r ON r.id = e.resident_id AND r.care_home_id = e.care_home_id
WHERE e.resident_id = :resident_id
  AND e.deleted_at IS NULL
  AND r.deleted_at IS NULL
  AND r.floor_id = e.floor_id
"""

_PARENT_EVENTS_SQL = (
    _PARENT_EVENT_BASE_SQL
    + """
  AND e.occurred_at >= COALESCE(
      CAST(:from_date AS TIMESTAMPTZ),
      '-infinity'::timestamptz
  )
  AND e.occurred_at < COALESCE(
      CAST(:to_date AS TIMESTAMPTZ),
      'infinity'::timestamptz
  )
ORDER BY e.occurred_at DESC, e.id DESC
LIMIT :limit
OFFSET :offset
"""
)

_PARENT_EVENT_BY_ID_SQL = (
    _PARENT_EVENT_BASE_SQL
    + """
  AND e.id = :source_id
"""
)

_OPTIONS_SQL = """
SELECT
    eo.care_event_id,
    tco.label,
    eo.note,
    eo.created_at
FROM care_event_options eo
JOIN care_template_options tco
    ON tco.id = eo.care_template_option_id
WHERE eo.care_event_id IN :event_ids
ORDER BY eo.care_event_id, eo.created_at, eo.id
"""

_MEASUREMENTS_SQL = """
SELECT
    em.care_event_id,
    tm.name,
    tm.unit,
    em.value_numeric,
    em.value_text,
    em.value_boolean,
    em.created_at
FROM care_event_measurements em
JOIN care_template_measurements tm
    ON tm.id = em.care_template_measurement_id
WHERE em.care_event_id IN :event_ids
ORDER BY em.care_event_id, em.created_at, em.id
"""


class CareEventEvidenceAdapter:
    source_type = EvidenceSourceType.CARE_EVENT

    def __init__(self, session: AsyncSession):
        self._session = session

    async def find(
        self,
        *,
        resident_id: uuid.UUID,
        from_date: datetime | None,
        to_date: datetime | None,
        topics: set[str] | None = None,
        statuses: set[str] | None = None,
        current_only: bool = False,
        limit: int,
    ) -> list[EvidenceDocument]:
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        for value in (from_date, to_date):
            if value is not None and value.utcoffset() is None:
                raise ValueError("date filters must be timezone-aware")
        if from_date is not None and to_date is not None and from_date >= to_date:
            raise ValueError("from_date must be earlier than to_date")
        allowed_statuses = {"completed", "declined", "refused", "not_applicable"}
        if statuses is not None and statuses - allowed_statuses:
            raise ValueError("unsupported care-event status")
        selected_statuses = allowed_statuses if statuses is None else statuses
        if current_only:
            # Completed care is observed evidence, not proof of a current care instruction.
            selected_statuses = selected_statuses & {"completed"}
        if not selected_statuses or topics == set():
            return []

        # Page until enough matching events are found. Filtering only the first
        # limited page could hide older relevant events behind unrelated entries.
        events = []
        offset = 0
        while len(events) < limit:
            parent_result = await self._session.execute(
                text(_PARENT_EVENTS_SQL),
                {
                    "resident_id": resident_id,
                    "from_date": from_date,
                    "to_date": to_date,
                    "limit": 500,
                    "offset": offset,
                },
            )
            page = parent_result.mappings().all()
            for event in page:
                if event["status"] not in selected_statuses:
                    continue
                if topics is not None and not topics.intersection(
                    _topics_for_event(event["category_name"], event["template_name"])
                ):
                    continue
                events.append(event)
                if len(events) == limit:
                    break
            if len(page) < 500:
                break
            offset += len(page)

        if not events:
            return []
        # After fetching the events we need to build the format to send
        # Creating the event ids
        event_ids = [event["id"] for event in events]
        options_by_event = await self._load_options(event_ids)
        measurements_by_event = await self._load_measurements(event_ids)
        return [
            self._document(
                event=event, options=options_by_event[event["id"]], measurements=measurements_by_event[event["id"]]
            )
            for event in events
        ]

    async def _load_options(self, event_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[dict[str, Any]]]:
        grouped = defaultdict(list)
        if not event_ids:
            return grouped
        # Creating optional statement from the sql
        options_statement = text(_OPTIONS_SQL).bindparams(bindparam("event_ids", expanding=True))
        options_result = await self._session.execute(
            options_statement,
            {"event_ids": event_ids},
        )

        for row in options_result.mappings().all():
            grouped[row["care_event_id"]].append(dict(row))
        return grouped

    async def _load_measurements(self, event_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[dict[str, Any]]]:
        grouped = defaultdict(list)
        if not event_ids:
            return grouped
        measurements_statement = text(_MEASUREMENTS_SQL).bindparams(bindparam("event_ids", expanding=True))
        measurements_result = await self._session.execute(
            measurements_statement,
            {"event_ids": event_ids},
        )

        for row in measurements_result.mappings().all():
            grouped[row["care_event_id"]].append(dict(row))
        return grouped

    async def get(
        self,
        *,
        resident_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> EvidenceDocument | None:
        result = await self._session.execute(
            text(_PARENT_EVENT_BY_ID_SQL),
            {
                "resident_id": resident_id,
                "source_id": source_id,
            },
        )

        event = result.mappings().one_or_none()

        if event is None:
            return None

        options_by_event = await self._load_options([event["id"]])
        measurements_by_event = await self._load_measurements([event["id"]])

        return self._document(
            event=event,
            options=options_by_event[event["id"]],
            measurements=measurements_by_event[event["id"]],
        )

    @staticmethod
    def _document(
        *,
        event: Mapping[str, Any],
        options: list[dict[str, Any]],
        measurements: list[dict[str, Any]],
    ) -> EvidenceDocument:
        category_name = _clean(event["category_name"]) or "Care record"
        template_name = _clean(event["template_name"]) or "Unnamed care event"
        status = str(event["status"])

        title = f"{category_name} — {template_name}"
        topics = _topics_for_event(category_name, template_name)

        option_metadata = [
            {
                "label": _clean(option["label"]),
                "note": _clean(option["note"]),
            }
            for option in options
        ]

        measurement_metadata = [
            {
                "name": _clean(measurement["name"]),
                "unit": _clean(measurement["unit"]),
                "value_numeric": measurement["value_numeric"],
                "value_text": _clean(measurement["value_text"]),
                "value_boolean": measurement["value_boolean"],
            }
            for measurement in measurements
        ]

        # Build local searchable/citation text from approved event content.
        text_parts = [
            f"{category_name}.",
            f"{template_name}.",
            f"Status: {status.replace('_', ' ')}.",
        ]

        if summary := _clean(event["summary"]):
            text_parts.append(summary)

        if note := _clean(event["note"]):
            text_parts.append(f"Note: {note}")

        for option in option_metadata:
            if option["label"]:
                part = f"Selected: {option['label']}."
                if option["note"]:
                    part += f" Detail: {option['note']}"
                text_parts.append(part)

        for measurement in measurements:
            value = _measurement_value(measurement)
            name = _clean(measurement["name"])

            if name and value is not None:
                text_parts.append(f"{name}: {value}.")

        # Any child creation/change makes a citation stale.
        version_times: list[datetime] = [event["updated_at"]]

        version_times.extend(option["created_at"] for option in options if option.get("created_at") is not None)
        version_times.extend(
            measurement["created_at"] for measurement in measurements if measurement.get("created_at") is not None
        )

        # Timestamps alone miss child edits/deletions and template label changes.
        # The evidence contract allows an opaque string revision.
        revision = json.dumps(
            {"event": dict(event), "options": options, "measurements": measurements},
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        )
        source_version = "sha256:" + hashlib.sha256(revision.encode()).hexdigest()

        return EvidenceDocument(
            evidence_id=f"care_event:{event['id']}",
            source_type=EvidenceSourceType.CARE_EVENT,
            source_id=event["id"],
            resident_id=event["resident_id"],
            care_home_id=event["care_home_id"],
            floor_id=event["floor_id"],
            occurred_at=event["occurred_at"],
            source_version=source_version,
            topic_tags=set(topics),
            authority_level=AuthorityLevel.CARE_EVENT,
            time_precision="timestamp",
            title=title,
            effective_from=None,
            effective_to=None,
            status=status,
            searchable_text=" ".join(text_parts),
            structured_metadata={
                "category": category_name,
                "template": template_name,
                "summary": _clean(event["summary"]),
                "note": _clean(event["note"]),
                "status": status,
                "template_id": str(event["template_id"]),
                "category_id": str(event["category_id"]),
                "last_recorded_update": max(version_times).isoformat(),
                "options": option_metadata,
                "measurements": measurement_metadata,
            },
            is_deleted=event["deleted_at"] is not None,
            is_eligible=event["deleted_at"] is None,
        )
