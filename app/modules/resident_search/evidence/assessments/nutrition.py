import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.resident_search.evidence.models import AuthorityLevel, EvidenceDocument, EvidenceSourceType

_SELECT = """
    SELECT
        n.id,
        n.resident_id,
        n.care_home_id,
        r.floor_id,
        n.assessment_tool,
        n.bmi_score,
        n.weight_loss_score,
        n.acute_disease_score,
        n.total_score,
        n.risk_level,
        n.action_plan,
        n.assessed_at,
        n.next_review_due,
        n.created_at,
        n.deleted_at
    FROM nutrition_risk_assessments n
    JOIN residents r
      ON r.id = n.resident_id
     AND r.care_home_id = n.care_home_id
    WHERE n.resident_id = :resident_id
      AND n.deleted_at IS NULL
      AND r.deleted_at IS NULL
      AND r.floor_id IS NOT NULL
"""

class NutritionAssessmentReader:
    def __init__(self, session: AsyncSession):
        self._session = session

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
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")

        if from_date is not None and to_date is not None and from_date >= to_date:
            raise ValueError("from_date must be earlier than to_date")

        # Every record returned by this reader is mobility evidence.
        supported_topics = {
            "nutrition",
            "hydration",
            "weight",
            "malnutrition",
            "intake",}
        if topics and not topics.intersection(supported_topics):
            return []

        # Assessment records are historical assessments, not active/completed events.
        if statuses and "assessed" not in statuses:
            return []

        query = text(
            _SELECT
            + """
                      AND n.assessed_at >= COALESCE(
                            CAST(:from_date AS TIMESTAMPTZ),
                            '-infinity'::timestamptz
                          )
                      AND n.assessed_at < COALESCE(
                            CAST(:to_date AS TIMESTAMPTZ),
                            'infinity'::timestamptz
                          )
                    ORDER BY n.assessed_at DESC, n.id DESC
                    LIMIT :limit
                    """
        )

        rows = (
            await self._session.execute(
                query,
                {
                    "resident_id": resident_id,
                    "from_date": from_date,
                    "to_date": to_date,
                    "limit": limit,
                },
            )
        ).mappings().all()

        documents = [self._document(row) for row in rows]

        # This table has no active/effective-period fields. “Current” means
        # “most recently assessed” only; it does not mean a current care-plan rule.
        if current_only:
            return documents[:1]

        return documents

    async def get(
        self,
        *,
        resident_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> EvidenceDocument | None:
        row = (
            await self._session.execute(
                text(_SELECT + " AND n.id = :source_id"),
                {
                    "resident_id": resident_id,
                    "source_id": source_id,
                },
            )
        ).mappings().one_or_none()

        return self._document(row) if row is not None else None

    @staticmethod
    def _document(row: Mapping[str, Any]) -> EvidenceDocument:
        risk_level = row["risk_level"]
        total_score = row["total_score"]
        bmi_score = row["bmi_score"]
        weight_loss_score = row["weight_loss_score"]
        acute_disease_score = row["acute_disease_score"]

        title = "Nutrition assessment"
        parts = [
            f"{row['assessment_tool']} nutrition risk assessment."
        ]

        if total_score is not None:
            parts.append(f"Total score: {total_score}.")

        if risk_level:
            parts.append(
                f"Risk level: {str(risk_level).replace('_', ' ')}."
            )

        # This is allowed in local evidence text only if your approved policy
        # permits it. It still requires minimisation/redaction before AI egress.
        if row["action_plan"]:
            action_plan = " ".join(str(row["action_plan"]).split())
            parts.append(f"Recorded action plan: {action_plan}")



        metadata = {
            "assessment_tool": row["assessment_tool"],
            "risk_level": risk_level,
            "total_score": total_score,
            "bmi_score": bmi_score,
            "weight_loss_score": weight_loss_score,
            "next_review_due": row["next_review_due"],
            "acute_disease_score" : acute_disease_score,
            "has_action_plan": bool(row["action_plan"]),
        }

        return EvidenceDocument(
            evidence_id=f"nutrition_assessment:{row['id']}",
            source_type=EvidenceSourceType.NUTRITION_ASSESSMENT,
            source_id=row["id"],

            resident_id=row["resident_id"],
            care_home_id=row["care_home_id"],
            floor_id=row["floor_id"],

            authority_level=AuthorityLevel.FORMAL_ASSESSMENT,
            topic_tags={
                "nutrition",
                "hydration",
                "weight",
                "malnutrition",
                "intake",
            },
            status="assessed",

            occurred_at=row["assessed_at"],
            time_precision="timestamp",
            effective_from=None,
            effective_to=None,

            # See source-version note below.
            source_version=row["created_at"],

            title=title,
            searchable_text=" ".join(parts),
            structured_metadata=metadata,

            is_deleted=row["deleted_at"] is not None,
            is_eligible=row["deleted_at"] is None,
            is_implausible=False
        )




