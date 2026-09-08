from app.modules.care_recording.events import CareEventRecorded
from app.workers.tasks.events import care_event_recorded


async def handle_care_event_recorded(
    event: CareEventRecorded,
) -> None:
    care_event_recorded.delay(
        event_id=str(event.event_id),
        care_home_id=str(event.care_home_id),
        actor_user_id=(
            str(event.actor_user_id)
            if event.actor_user_id
            else None
        ),
        care_event_id=str(event.care_event_id),
        resident_id=str(event.resident_id),
        template_id=str(event.template_id),
        status=event.status,
    )