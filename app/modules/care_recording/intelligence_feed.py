"""Read-only care-event projection under the caller's tenant/floor RLS session."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Correlated aggregates prevent option/measurement joins multiplying event rows.
CARE_EVENT_SQL = """
SELECT e.id, e.resident_id, 'note' AS type, e.occurred_at AS recorded_at,
       e.recorded_by, false AS is_implausible, 'care_events' AS source_type,
       'timestamp' AS time_precision, NULL::text AS source_date,
       jsonb_build_object(
         'template_id', e.template_id, 'template_name', t.name,
         'category_id', e.category_id, 'category_name', c.name,
         'status', e.status, 'note', e.note, 'summary', e.summary,
         'duration_minutes', e.duration_minutes,
         'created_at', e.created_at, 'updated_at', e.updated_at,
         'template_updated_at', t.updated_at, 'category_updated_at', c.updated_at,
         'options', COALESCE((
           SELECT jsonb_agg(jsonb_build_object(
             'option_id', o.id, 'section_id', s.id, 'section_name', s.name,
             'value_code', o.value_code, 'label', o.label, 'note', v.note,
             'option_updated_at', o.updated_at, 'section_updated_at', s.updated_at
           ) ORDER BY s.sort_order, o.sort_order, o.id)
           FROM care_event_options v
           JOIN care_template_options o ON o.id = v.care_template_option_id
           JOIN care_template_sections s ON s.id = o.section_id
           WHERE v.care_event_id = e.id AND v.care_home_id = e.care_home_id
             AND s.template_id = e.template_id
             AND (o.care_home_id IS NULL OR o.care_home_id = e.care_home_id)
             AND (s.care_home_id IS NULL OR s.care_home_id = e.care_home_id)
         ), '[]'::jsonb),
         'measurements', COALESCE((
           SELECT jsonb_agg(jsonb_build_object(
             'measurement_id', m.id, 'name', m.name, 'unit', m.unit,
             'value_numeric', v.value_numeric, 'value_text', v.value_text,
             'value_boolean', v.value_boolean, 'definition_updated_at', m.updated_at
           ) ORDER BY m.sort_order, m.id)
           FROM care_event_measurements v
           JOIN care_template_measurements m ON m.id = v.care_template_measurement_id
           WHERE v.care_event_id = e.id AND v.care_home_id = e.care_home_id
             AND m.template_id = e.template_id
             AND (m.care_home_id IS NULL OR m.care_home_id = e.care_home_id)
         ), '[]'::jsonb)
       ) AS value
FROM care_events e
JOIN residents r ON r.id = e.resident_id AND r.care_home_id = e.care_home_id
JOIN care_templates t ON t.id = e.template_id
JOIN care_categories c ON c.id = e.category_id
WHERE e.care_home_id = :tenant_id AND e.resident_id = :resident_id
  AND e.deleted_at IS NULL AND r.deleted_at IS NULL
  AND (t.care_home_id IS NULL OR t.care_home_id = e.care_home_id)
  AND e.occurred_at >= :since AND e.occurred_at < :until
ORDER BY e.occurred_at, e.id
LIMIT :limit OFFSET :offset
"""


async def list_care_events(
    session: AsyncSession, *, tenant_id: UUID, resident_id: UUID,
    since: datetime, until: datetime, limit: int, offset: int,
) -> list[dict]:
    rows = await session.execute(text(CARE_EVENT_SQL), {
        "tenant_id": tenant_id, "resident_id": resident_id,
        "since": since, "until": until, "limit": limit, "offset": offset,
    })
    return [dict(row) for row in rows.mappings()]
