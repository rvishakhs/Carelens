"""Current resident care-needs evidence read through the caller's RLS session.

These records describe standing support requirements rather than one-off care
events.  They are therefore deliberately modelled as ``CARE_NEED`` authority,
with effective dates retained alongside the audit timestamp.  They are local
retrieval projections only: narrative fields must still pass the gateway's
minimisation and pseudonymisation controls before any model egress.
"""

import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.resident_search.evidence.models import (
    AuthorityLevel,
    EvidenceDocument,
    EvidenceSourceType,
)
from app.modules.resident_search.evidence.utils import _clean


_CONFIG: dict[EvidenceSourceType, dict[str, Any]] = {
    EvidenceSourceType.COMMUNICATION_NEED: {
        "table": "communication_needs",
        "alias": "n",
        "title": "Communication needs",
        "topics": {"communication", "hearing", "vision", "cognitive_support"},
        "time_column": "updated_at",
        "effective_from": "NULL::date",
        "effective_to": "NULL::date",
        "has_effective_from": False,
        "has_effective_to": False,
        "columns": """
            n.primary_method, n.hearing_impairment, n.hearing_aid_used,
            n.visual_impairment, n.glasses_used, n.cognitive_considerations,
            n.interpreter_language, n.aac_tools, n.notes
        """,
    },
    EvidenceSourceType.NUTRITION_TARGET: {
        "table": "nutrition_hydration_targets",
        "alias": "n",
        "title": "Nutrition and hydration target",
        "topics": {"nutrition", "hydration", "fluid_target", "calorie_target"},
        "time_column": "updated_at",
        "effective_from": "n.effective_from",
        "effective_to": "n.effective_to",
        "has_effective_from": True,
        "has_effective_to": True,
        "columns": "n.daily_fluid_target_ml, n.daily_calorie_target",
    },
    EvidenceSourceType.CONTINENCE_CARE_PLAN: {
        "table": "continence_care_plans",
        "alias": "n",
        "title": "Continence care plan",
        "topics": {"continence", "toileting", "personal_care"},
        "time_column": "updated_at",
        "effective_from": "n.effective_from",
        "effective_to": "NULL::date",
        "has_effective_from": True,
        "has_effective_to": False,
        "columns": "n.toileting_schedule, n.product_regime, n.bowel_management_plan",
    },
}


class CareNeedsEvidenceAdapter:
    """Adapter for one explicit care-needs source type.

    Keeping source identity concrete means every citation can reopen precisely
    the record used by retrieval, while the caller can register three instances
    behind the common adapter protocol.
    """

    def __init__(self, session: AsyncSession, source_type: EvidenceSourceType):
        if source_type not in _CONFIG:
            raise ValueError(f"{source_type.value} is not a care-needs source")
        self._session = session
        self.source_type = source_type
        self._config = _CONFIG[source_type]

    def _base_sql(self) -> str:
        c = self._config
        return f"""
            SELECT n.id, n.resident_id, n.care_home_id, r.floor_id,
                   n.created_at, n.updated_at, n.deleted_at,
                   {c['effective_from']} AS effective_from,
                   {c['effective_to']} AS effective_to,
                   {c['columns']}
            FROM {c['table']} n
            JOIN residents r ON r.id = n.resident_id AND r.care_home_id = n.care_home_id
            WHERE n.resident_id = :resident_id
              AND n.deleted_at IS NULL
              AND r.deleted_at IS NULL
              AND r.floor_id IS NOT NULL
        """

    async def find(
        self,
        *,
        resident_id: uuid.UUID,
        from_date: datetime | None,
        to_date: datetime | None,
        limit: int,
        topics: set[str] | None = None,
        statuses: set[str] | None = None,
        current_only: bool = False,
    ) -> list[EvidenceDocument]:
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        if from_date is not None and to_date is not None and from_date >= to_date:
            raise ValueError("from_date must be earlier than to_date")
        if topics and not self._config["topics"].intersection({topic.casefold() for topic in topics}):
            return []
        if statuses and "active" not in {status.casefold() for status in statuses}:
            return []

        sql = self._base_sql()
        params: dict[str, Any] = {"resident_id": resident_id, "limit": limit}
        # A current requirement remains relevant even if it predates a request's
        # history range.  Historical mode honours the supplied range.
        if not current_only:
            sql += " AND n.updated_at >= COALESCE(CAST(:from_date AS TIMESTAMPTZ), '-infinity'::timestamptz)"
            sql += " AND n.updated_at < COALESCE(CAST(:to_date AS TIMESTAMPTZ), 'infinity'::timestamptz)"
            params.update(from_date=from_date, to_date=to_date)
        else:
            if self._config["has_effective_from"]:
                sql += " AND n.effective_from <= CURRENT_DATE"
            if self._config["has_effective_to"]:
                sql += " AND (n.effective_to IS NULL OR n.effective_to >= CURRENT_DATE)"
        sql += " ORDER BY n.updated_at DESC, n.id DESC LIMIT :limit"

        rows = (await self._session.execute(text(sql), params)).mappings().all()
        documents = [self._document(row) for row in rows]
        return documents[:1] if current_only else documents

    async def get(self, *, resident_id: uuid.UUID, source_id: uuid.UUID) -> EvidenceDocument | None:
        row = (
            await self._session.execute(
                text(self._base_sql() + " AND n.id = :source_id"),
                {"resident_id": resident_id, "source_id": source_id},
            )
        ).mappings().one_or_none()
        return self._document(row) if row is not None else None

    def _document(self, row: Mapping[str, Any]) -> EvidenceDocument:
        if self.source_type is EvidenceSourceType.COMMUNICATION_NEED:
            metadata = {
                key: row[key]
                for key in (
                    "primary_method", "hearing_impairment", "hearing_aid_used",
                    "visual_impairment", "glasses_used", "cognitive_considerations",
                    "interpreter_language", "aac_tools",
                )
            }
            parts = ["Communication needs.", f"Primary method: {row['primary_method']!s}."]
            for label, key in (("Cognitive considerations", "cognitive_considerations"), ("Interpreter language", "interpreter_language"), ("AAC tools", "aac_tools")):
                if value := _clean(row[key]):
                    parts.append(f"{label}: {value}.")
            for label, key in (("Hearing impairment", "hearing_impairment"), ("Hearing aid used", "hearing_aid_used"), ("Visual impairment", "visual_impairment"), ("Glasses used", "glasses_used")):
                parts.append(f"{label}: {'Yes' if row[key] else 'No'}.")
        elif self.source_type is EvidenceSourceType.NUTRITION_TARGET:
            metadata = {"daily_fluid_target_ml": row["daily_fluid_target_ml"], "daily_calorie_target": row["daily_calorie_target"]}
            parts = ["Nutrition and hydration target."]
            if row["daily_fluid_target_ml"] is not None:
                parts.append(f"Daily fluid target: {row['daily_fluid_target_ml']} ml.")
            if row["daily_calorie_target"] is not None:
                parts.append(f"Daily calorie target: {row['daily_calorie_target']} kcal.")
        else:
            metadata = {key: row[key] for key in ("toileting_schedule", "product_regime", "bowel_management_plan")}
            parts = ["Continence care plan."]
            for label, key in (("Toileting schedule", "toileting_schedule"), ("Product regime", "product_regime"), ("Bowel management plan", "bowel_management_plan")):
                if value := _clean(row[key]):
                    parts.append(f"{label}: {value}.")

        return EvidenceDocument(
            evidence_id=f"{self.source_type.value}:{row['id']}", source_type=self.source_type, source_id=row["id"],
            resident_id=row["resident_id"], care_home_id=row["care_home_id"], floor_id=row["floor_id"],
            authority_level=AuthorityLevel.CARE_NEED, topic_tags=set(self._config["topics"]), status="active",
            occurred_at=row["updated_at"], time_precision="timestamp", source_date=None,
            effective_from=row["effective_from"], effective_to=row["effective_to"], source_version=row["updated_at"],
            title=self._config["title"], searchable_text=" ".join(parts), structured_metadata=metadata,
            is_deleted=row["deleted_at"] is not None, is_eligible=row["deleted_at"] is None,
        )
