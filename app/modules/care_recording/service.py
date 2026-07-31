import uuid

from app.modules.care_recording.events import CareEventRecorded
from app.modules.care_recording.models import CareEvent
from app.modules.care_recording.repository import CareRecordingRepository
from app.modules.care_recording.schemas import CareEventCreate
from app.shared.events import EventBus
from app.shared.exceptions import NotFoundError


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
