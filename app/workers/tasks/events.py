from app import celery_app


@celery_app.task(
    name="carelens.events.care_event_recorded",
    queue="carelens.default",
)
def care_event_recorded(
    event_id: str,
    care_home_id: str,
    actor_user_id: str | None,
    care_event_id: str,
    resident_id: str,
    template_id: str,
    status: str,
) -> None:
    print(
        f"Processing CareEventRecorded "
        f"event={event_id} "
        f"care_event={care_event_id}"
    )

