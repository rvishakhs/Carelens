import uuid

from app import EventBus, NotFoundError, ResidentHistorySearched
from app.modules.resident_search.repository import ResidentSearchRepository
from app.modules.resident_search.schemas import (
    ResidentSearchRequest,
    ResidentSearchResponse,
    SearchSourceType,
)


class ResidentSearchService:
    def __init__(self, repository: ResidentSearchRepository, event_bus: EventBus):
        self._repository = repository
        self._event_bus = event_bus

    async def search(
        self,
        care_home_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        resident_id: uuid.UUID,
        payload: ResidentSearchRequest,
    ) -> ResidentSearchResponse:
        if not await self._repository.resident_exists(resident_id):
            raise NotFoundError(f"resident {resident_id} not found")

        requested_sources = set(payload.source_types or list(SearchSourceType))
        evidence = []

        # First deterministic search handler.
        if SearchSourceType.FALL in requested_sources:
            evidence.extend(
                await self._repository.find_falls(
                    resident_id,
                    payload.from_date,
                    payload.to_date,
                )
            )

        evidence.sort(key=lambda item: item.occurred_at, reverse=True)

        response = ResidentSearchResponse(
            resident_id=resident_id,
            query=payload.query,
            result_summary=f"Found {len(evidence)} matching record(s).",
            evidence=evidence,
            coverage_limitations=[
                "This result currently searches approved fall records only.",
                "Verify details against the cited source record.",
            ],
        )
        await self._event_bus.publish(
            ResidentHistorySearched(
                care_home_id=care_home_id,
                actor_user_id=actor_user_id,
                resident_id=resident_id,
                result_count=len(evidence),
            )
        )
        return response
