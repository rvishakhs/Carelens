import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.care_recording.models import (
    CareCategory,
    CareEvent,
    CareEventMeasurement,
    CareEventOption,
    CareTemplate,
    CareTemplateMeasurement,
    CareTemplateOption,
    CareTemplateSection,
)
from app.modules.care_recording.ports import CareEventReader
from app.modules.care_recording.schemas import CareEventRead


class CareRecordingRepository(CareEventReader):
    """RLS does the home/global filtering on template tables (global_or_tenant_select,
    migrations/versions/0014) -- these queries never add their own care_home_id
    predicate, the same way every other RLS-backed repository in this codebase
    doesn't either."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_categories(self) -> list[CareCategory]:
        result = await self._session.execute(
            select(CareCategory)
            .where(CareCategory.is_active, CareCategory.deleted_at.is_(None))
            .order_by(CareCategory.sort_order)
        )
        return list(result.scalars().all())

    async def list_templates_by_category(self, category_id: uuid.UUID) -> list[CareTemplate]:
        result = await self._session.execute(
            select(CareTemplate)
            .where(
                CareTemplate.category_id == category_id,
                CareTemplate.is_active,
                CareTemplate.deleted_at.is_(None),
            )
            .order_by(CareTemplate.sort_order)
            .options(
                selectinload(CareTemplate.sections).selectinload(CareTemplateSection.options),
                selectinload(CareTemplate.measurements),
            )
        )
        return list(result.scalars().all())

    async def get_template_detail(self, template_id: uuid.UUID) -> CareTemplate | None:
        result = await self._session.execute(
            select(CareTemplate)
            .where(CareTemplate.id == template_id, CareTemplate.deleted_at.is_(None))
            .options(
                selectinload(CareTemplate.sections).selectinload(CareTemplateSection.options),
                selectinload(CareTemplate.measurements),
            )
        )
        return result.scalar_one_or_none()

    async def create_event(
        self,
        event: CareEvent,
        option_ids: list[tuple[uuid.UUID, str | None]],
        measurements: list[tuple[uuid.UUID, float | None, str | None, bool | None]],
    ) -> CareEvent:
        self._session.add(event)
        await self._session.flush()

        for option_id, note in option_ids:
            self._session.add(
                CareEventOption(
                    care_home_id=event.care_home_id,
                    care_event_id=event.id,
                    care_template_option_id=option_id,
                    note=note,
                )
            )
        for measurement_id, value_numeric, value_text, value_boolean in measurements:
            self._session.add(
                CareEventMeasurement(
                    care_home_id=event.care_home_id,
                    care_event_id=event.id,
                    care_template_measurement_id=measurement_id,
                    value_numeric=value_numeric,
                    value_text=value_text,
                    value_boolean=value_boolean,
                )
            )
        await self._session.flush()
        return event

    async def get_recent_for_resident(self, resident_id: uuid.UUID, hours: int = 24) -> list[CareEventRead]:
        since = datetime.now(UTC) - timedelta(hours=hours)
        result = await self._session.execute(
            select(CareEvent)
            .where(CareEvent.resident_id == resident_id, CareEvent.occurred_at >= since, CareEvent.deleted_at.is_(None))
            .order_by(CareEvent.occurred_at.desc())
        )
        return [CareEventRead.model_validate(e) for e in result.scalars().all()]

    async def list_history_for_resident(self, resident_id: uuid.UUID, limit: int = 100) -> list[dict]:
        """Denormalised history for the Care Records tile view -- see
        CareEventHistoryItem's docstring for why this joins template/category names
        and pulls option labels + measurement values up front instead of leaving the
        frontend to re-fetch template detail per tile."""
        event_rows = (
            await self._session.execute(
                select(
                    CareEvent.id,
                    CareEvent.occurred_at,
                    CareEvent.status,
                    CareEvent.note,
                    CareEvent.summary,
                    CareEvent.duration_minutes,
                    CareEvent.recorded_by,
                    CareTemplate.name.label("template_name"),
                    CareCategory.name.label("category_name"),
                    CareCategory.icon.label("category_icon"),
                )
                .join(CareTemplate, CareTemplate.id == CareEvent.template_id)
                .join(CareCategory, CareCategory.id == CareEvent.category_id)
                .where(CareEvent.resident_id == resident_id, CareEvent.deleted_at.is_(None))
                .order_by(CareEvent.occurred_at.desc())
                .limit(limit)
            )
        ).all()

        event_ids = [row.id for row in event_rows]
        if not event_ids:
            return []

        # identity.models isn't importable here (module-boundary rule -- see
        # walkthrough.md's "the rule this enforces"), so this resolves display names
        # via the users table by name rather than the ORM model.
        recorder_ids = list({row.recorded_by for row in event_rows if row.recorded_by is not None})
        names_by_user_id: dict[uuid.UUID, str] = {}
        if recorder_ids:
            name_stmt = text("SELECT id, display_name FROM users WHERE id IN :ids").bindparams(
                bindparam("ids", expanding=True)
            )
            name_rows = (await self._session.execute(name_stmt, {"ids": recorder_ids})).all()
            names_by_user_id = {row.id: row.display_name for row in name_rows}

        option_rows = (
            await self._session.execute(
                select(CareEventOption.care_event_id, CareTemplateOption.label, CareEventOption.note)
                .join(CareTemplateOption, CareTemplateOption.id == CareEventOption.care_template_option_id)
                .where(CareEventOption.care_event_id.in_(event_ids))
            )
        ).all()

        measurement_rows = (
            await self._session.execute(
                select(
                    CareEventMeasurement.care_event_id,
                    CareTemplateMeasurement.name,
                    CareTemplateMeasurement.unit,
                    CareEventMeasurement.value_numeric,
                    CareEventMeasurement.value_text,
                    CareEventMeasurement.value_boolean,
                )
                .join(CareTemplateMeasurement, CareTemplateMeasurement.id == CareEventMeasurement.care_template_measurement_id)
                .where(CareEventMeasurement.care_event_id.in_(event_ids))
            )
        ).all()

        options_by_event: dict[uuid.UUID, list[dict]] = {}
        for row in option_rows:
            options_by_event.setdefault(row.care_event_id, []).append({"label": row.label, "note": row.note})

        measurements_by_event: dict[uuid.UUID, list[dict]] = {}
        for row in measurement_rows:
            measurements_by_event.setdefault(row.care_event_id, []).append(
                {
                    "name": row.name,
                    "unit": row.unit,
                    "value_numeric": row.value_numeric,
                    "value_text": row.value_text,
                    "value_boolean": row.value_boolean,
                }
            )

        return [
            {
                "id": row.id,
                "template_name": row.template_name,
                "category_name": row.category_name,
                "category_icon": row.category_icon,
                "occurred_at": row.occurred_at,
                "status": row.status,
                "note": row.note,
                "summary": row.summary,
                "duration_minutes": row.duration_minutes,
                "recorded_by_name": names_by_user_id.get(row.recorded_by) if row.recorded_by else None,
                "options": options_by_event.get(row.id, []),
                "measurements": measurements_by_event.get(row.id, []),
            }
            for row in event_rows
        ]
