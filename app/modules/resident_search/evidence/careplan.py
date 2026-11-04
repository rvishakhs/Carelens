import uuid
from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.resident_search.evidence.models import (
    AuthorityLevel,
    EvidenceDocument,
    EvidenceSourceType,
)
from app.modules.resident_search.evidence.utils import (
    _care_plan_revision,
    _clean,
    _topics_for_care_plan,
)

CAREPLAN_BASE_SQL = """
SELECT
    cp.id AS care_plan_id,
    cp.resident_id,
    cp.care_home_id,
    r.floor_id,
    cp.domain,
    cp.goal AS plan_goal,
    cp.current_version,
    cp.review_due,
    cp.is_active,
    cp.updated_at AS plan_updated_at,

    cpv.id AS version_id,
    cpv.version_number,
    cpv.content,
    cpv.created_at AS version_created_at,
    cpv.change_reason
FROM care_plans cp
JOIN residents r
  ON r.id = cp.resident_id
 AND r.care_home_id = cp.care_home_id
JOIN care_plan_versions cpv
  ON cpv.care_plan_id = cp.id
 AND cpv.care_home_id = cp.care_home_id
 AND cpv.version_number = cp.current_version
WHERE cp.resident_id = :resident_id
  AND cp.deleted_at IS NULL
  AND cp.is_active = TRUE
  AND cpv.deleted_at IS NULL
  AND r.deleted_at IS NULL
  AND r.floor_id IS NOT NULL
"""

CAREPLAN_FIND_SQL = (
    CAREPLAN_BASE_SQL
    + """
ORDER BY cp.domain ASC, cp.id ASC
LIMIT :limit OFFSET :offset
"""
)

CAREPLAN_BY_ID_SQL = (
    CAREPLAN_BASE_SQL
    + """
  AND cp.id = :source_id
"""
)

CARE_PLAN_DETAILS_SQL = """
SELECT
    g.id,
    g.care_plan_id,
    g.goal_text,
    g.baseline,
    g.target,
    g.measurement,
    g.status,
    g.set_at,
    g.review_date,
    g.achieved_date,
    g.created_at,
    g.updated_at
FROM care_plan_goals g
JOIN care_plans cp
  ON cp.id = g.care_plan_id
 AND cp.resident_id = g.resident_id
 AND cp.care_home_id = g.care_home_id
WHERE g.care_plan_id IN :plan_ids
  AND g.deleted_at IS NULL
  AND cp.deleted_at IS NULL
  AND cp.is_active = TRUE
ORDER BY g.care_plan_id, g.set_at ASC, g.id ASC
"""

_ALLOWED_STATUSES = frozenset({"active"})


def _validate_find_request(
    *,
    from_date: datetime | None,
    to_date: datetime | None,
    limit: int,
    statuses: set[str] | None,
) -> set[str]:
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")

    for value in (from_date, to_date):
        if value is not None and value.utcoffset() is None:
            raise ValueError("date filters must be timezone-aware")

    if from_date is not None and to_date is not None and from_date >= to_date:
        raise ValueError("from_date must be earlier than to_date")

    selected_statuses = {"active"} if statuses is None else statuses

    unsupported = selected_statuses - _ALLOWED_STATUSES
    if unsupported:
        raise ValueError("Care-plan search currently supports only active plans")

    return selected_statuses


class CarePlanEvidenceAdapter:
    """Current active plans and their live goals, read through an RLS session.

    Both values of current_only retrieve the current version in phase one.
    Valid date bounds do not exclude an older plan that remains active; this
    adapter does not reconstruct historical versions or historical goal state.
    """

    source_type = EvidenceSourceType.CARE_PLAN

    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _normalise_topics(topics: set[str] | None) -> set[str] | None:
        if topics is None:
            return None

        return {topic.strip().casefold() for topic in topics if topic.strip()}

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
        selected_statuses = _validate_find_request(
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            statuses=statuses,
        )

        normalised_topics = self._normalise_topics(topics)
        if not selected_statuses or normalised_topics == set():
            return []

        documents = []
        offset = 0
        # Filter before applying the result limit. Relevant plans can occur
        # after unrelated domains, and topic tags can come from linked goals.
        while len(documents) < limit:
            plan_rows = await self._load_current_active_plans(
                resident_id=resident_id,
                limit=limit,
                offset=offset,
            )
            if not plan_rows:
                break
            goals_by_plan = await self._load_goals([plan["care_plan_id"] for plan in plan_rows])
            for plan in plan_rows:
                document = self._document(plan=plan, goals=goals_by_plan.get(plan["care_plan_id"], []))
                if normalised_topics is None or document.topic_tags.intersection(normalised_topics):
                    documents.append(document)
                    if len(documents) == limit:
                        break
            if len(plan_rows) < limit:
                break
            offset += len(plan_rows)
        return documents

    async def _load_current_active_plans(
        self,
        *,
        resident_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        result = await self._session.execute(
            text(CAREPLAN_FIND_SQL),
            {
                "resident_id": resident_id,
                "limit": limit,
                "offset": offset,
            },
        )
        return [dict(row) for row in result.mappings().all()]

    async def _load_goals(
        self,
        plan_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, list[dict[str, Any]]]:
        grouped: dict[uuid.UUID, list[dict[str, Any]]] = defaultdict(list)

        if not plan_ids:
            return grouped

        statement = text(CARE_PLAN_DETAILS_SQL).bindparams(bindparam("plan_ids", expanding=True))

        result = await self._session.execute(
            statement,
            {"plan_ids": plan_ids},
        )

        for row in result.mappings().all():
            grouped[row["care_plan_id"]].append(dict(row))

        return grouped

    async def get(
        self,
        *,
        resident_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> EvidenceDocument | None:

        result = await self._session.execute(
            text(CAREPLAN_BY_ID_SQL),
            {
                "resident_id": resident_id,
                "source_id": source_id,
            },
        )
        plan = result.mappings().one_or_none()

        if plan is None:
            return None

        goals_by_plan = await self._load_goals([plan["care_plan_id"]])

        return self._document(
            plan=plan,
            goals=goals_by_plan.get(plan["care_plan_id"], []),
        )

    @staticmethod
    def _document(
        *,
        plan: Mapping[str, Any],
        goals: list[dict[str, Any]],
    ) -> EvidenceDocument:

        domain = str(plan["domain"])
        content = _clean(plan["content"]) or ""
        plan_goal = _clean(plan["plan_goal"])

        topics = _topics_for_care_plan(
            domain=domain,
            content=content,
            goals=goals,
        )

        title = f"{domain.replace('_', ' ').title()} care plan"

        text_parts = [
            f"Current active {domain.replace('_', ' ')} care plan.",
        ]

        if plan_goal:
            text_parts.append(f"Plan goal: {plan_goal}.")

        if content:
            text_parts.append(f"Instructions: {content}")

        for goal in goals:
            text_parts.append(f"Care goal status: {str(goal['status']).replace('_', ' ')}.")
            goal_text = _clean(goal["goal_text"])
            baseline = _clean(goal["baseline"])
            target = _clean(goal["target"])
            measurement = _clean(goal["measurement"])

            if goal_text:
                text_parts.append(f"Care goal: {goal_text}.")
            if baseline:
                text_parts.append(f"Baseline: {baseline}.")
            if target:
                text_parts.append(f"Target: {target}.")
            if measurement:
                text_parts.append(f"Measurement: {measurement}.")

        source_version = _care_plan_revision(
            plan=plan,
            goals=goals,
        )

        return EvidenceDocument(
            evidence_id=f"care_plan:{plan['care_plan_id']}",
            source_type=EvidenceSourceType.CARE_PLAN,
            source_id=plan["care_plan_id"],
            topic_tags=set(topics),
            authority_level=AuthorityLevel.CARE_PLAN,
            status="active" if plan["is_active"] else "inactive",
            occurred_at=plan["version_created_at"],
            # This is the version's recorded creation time. No effective dates
            # are present in the source schema, so do not infer them.
            time_precision="timestamp",
            effective_from=None,
            effective_to=None,
            source_version=source_version,
            resident_id=plan["resident_id"],
            care_home_id=plan["care_home_id"],
            floor_id=plan["floor_id"],
            title=title,
            searchable_text=" ".join(text_parts),
            structured_metadata={
                "domain": domain,
                "plan_goal": plan_goal,
                "current_version": plan["current_version"],
                "version_id": str(plan["version_id"]),
                "version_number": plan["version_number"],
                "content": content,
                "change_reason": _clean(plan["change_reason"]),
                "review_due": plan["review_due"],
                "goals": goals,
            },
            is_deleted=False,
            is_eligible=True,
        )
