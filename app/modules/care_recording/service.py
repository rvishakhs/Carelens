import uuid

from app.modules.care_recording.events import CareEventRecorded
from app.modules.care_recording.models import CareEvent, CareTemplate
from app.modules.care_recording.repository import CareRecordingRepository
from app.modules.care_recording.schemas import CareEventCreate
from app.shared.events import EventBus
from app.shared.exceptions import NotFoundError


def _measurement_value_text(value_numeric: float | None, value_text: str | None, value_boolean: bool | None, unit: str | None) -> str | None:
    if value_numeric is not None:
        return f"{value_numeric}{unit or ''}"
    if value_text is not None:
        return value_text
    if value_boolean is not None:
        return "Yes" if value_boolean else "No"
    return None


def _build_summary(template: CareTemplate, data: CareEventCreate) -> str:
    """Every recorded event gets this narrative sentence, not just ones where staff
    typed a free-text note -- it's the plain-language description of what a template
    tap-through actually selected (e.g. "Breakfast: Cereal, Porridge; Amount Eaten:
    Most. Percentage Eaten: 80%."), so a future embedding pipeline always has
    something meaningful to vectorise even when `note` is empty."""
    measurement_by_id = {measurement.id: measurement for measurement in template.measurements}
    selected_option_ids = {o.care_template_option_id for o in data.options}

    parts = [template.name]
    if data.status != "completed":
        parts[0] += f" ({data.status.replace('_', ' ')})"

    # Grouped by section (e.g. "Food: Cereal, Porridge" / "Amount Eaten: Most") rather
    # than one flat list, so which section a selection came from isn't lost.
    for section in template.sections:
        labels = [option.label for option in section.options if option.id in selected_option_ids]
        if labels:
            parts.append(f"{section.name}: {', '.join(labels)}")

    for m in data.measurements:
        measurement = measurement_by_id.get(m.care_template_measurement_id)
        if measurement is None:
            continue
        value_text = _measurement_value_text(m.value_numeric, m.value_text, m.value_boolean, measurement.unit)
        if value_text is not None:
            parts.append(f"{measurement.name}: {value_text}")

    summary = ". ".join(parts) + "."
    if data.note:
        summary += f" {data.note}"
    return summary


class CareRecordingService:
    def __init__(self, repository: CareRecordingRepository, event_bus: EventBus):
        self._repository = repository
        self._event_bus = event_bus

    async def record_care_event(
        self, care_home_id: uuid.UUID, actor_user_id: uuid.UUID, data: CareEventCreate
    ) -> CareEvent:
        template = await self._repository.get_template_detail(data.template_id)
        if template is None:
            raise NotFoundError(f"care template {data.template_id} not found")

        event = CareEvent(
            care_home_id=care_home_id,
            resident_id=data.resident_id,
            template_id=data.template_id,
            category_id=template.category_id,
            recorded_by=actor_user_id,
            status=data.status,
            note=data.note,
            duration_minutes=data.duration_minutes,
            summary=_build_summary(template, data),
            **({"occurred_at": data.occurred_at} if data.occurred_at else {}),
        )
        event = await self._repository.create_event(
            event,
            option_ids=[(o.care_template_option_id, o.note) for o in data.options],
            measurements=[
                (m.care_template_measurement_id, m.value_numeric, m.value_text, m.value_boolean)
                for m in data.measurements
            ],
        )

        await self._event_bus.publish(
            CareEventRecorded(
                care_home_id=care_home_id,
                actor_user_id=actor_user_id,
                care_event_id=event.id,
                resident_id=event.resident_id,
                template_id=event.template_id,
                status=event.status,
            )
        )
        return event
