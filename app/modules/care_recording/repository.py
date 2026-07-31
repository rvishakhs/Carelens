import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.care_recording.models import (
    CareCategory,
    CareEvent,
    CareEventMeasurement,
    CareEventOption,
    CareTemplate,
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

    async def list_for_resident(self, resident_id: uuid.UUID, limit: int = 100) -> list[CareEvent]:
        result = await self._session.execute(
            select(CareEvent)
            .where(CareEvent.resident_id == resident_id, CareEvent.deleted_at.is_(None))
            .order_by(CareEvent.occurred_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
