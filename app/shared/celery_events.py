# app/shared/celery_event_bus.py

from collections import defaultdict

from app import CareEventRecorded
from app import DomainEvent, EventBus
from app import care_event_recorded


EVENT_TASKS = {
    CareEventRecorded: care_event_recorded,
}

class CeleryEventBus(EventBus):

    def __init__(self) -> None:
        self._handlers = defaultdict(list)

    def subscribe(self, event_type, handler) -> None:
        self._handlers[event_type].append(handler)

    async def publish(self, event: DomainEvent) -> None:
        task = EVENT_TASKS.get(type(event))

        if task is None:
            return
        task.delay(
            event_id=str(event.event_id),
            care_home_id=str(event.care_home_id),
            care_event_id=str(event.care_event_id),
        )