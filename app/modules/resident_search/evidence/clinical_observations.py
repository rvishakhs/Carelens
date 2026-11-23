

import hashlib
import json
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.observations.repository import ObservationRepository
from app.modules.observations.schemas import ObservationRead
from app.modules.resident_search.evidence.models import (
    AuthorityLevel, EvidenceDocument, EvidenceRetrievalResult, EvidenceSourceType, PlausibilityPolicy,
)

PAGE_SIZE = 100
MAX_SCAN_ROWS = 1000


# Falls are intentionally absent: FallsEvidenceAdapter supplies the richer,
# authoritative fall projection and prevents duplicate evidence/citations.
_SOURCES: dict[EvidenceSourceType, frozenset[str]] = {
    EvidenceSourceType.OBSERVATION: frozenset({"observations", "pain_assessments", "vital_signs_records"}),
    EvidenceSourceType.SLEEP: frozenset({"sleep_records"}),
    EvidenceSourceType.NUTRITION: frozenset({"food_intake_records", "fluid_intake_records", "weight_records"}),
    EvidenceSourceType.MOBILITY: frozenset({"mobility_observations"}),
    EvidenceSourceType.WELLBEING: frozenset({"wellbeing_records", "behaviour_records"}),
    EvidenceSourceType.COMMUNICATION: frozenset({"communication_logs"}),
    EvidenceSourceType.WOUND: frozenset({"wound_records"}),
    EvidenceSourceType.INCIDENT: frozenset({"incidents"}),
}

_DISPLAY = {
    "observations": ("Observation", {"observation"}),
    "sleep_records": ("Sleep record", {"sleep", "night_routine"}),
    "food_intake_records": ("Food intake", {"nutrition", "meal", "food_intake"}),
    "fluid_intake_records": ("Fluid intake", {"nutrition", "hydration", "fluid_intake"}),
    "weight_records": ("Weight record", {"nutrition", "weight"}),
    "mobility_observations": ("Mobility observation", {"mobility", "transfer"}),
    "wellbeing_records": ("Wellbeing record", {"wellbeing", "mood"}),
    "behaviour_records": ("Behaviour record", {"wellbeing", "behaviour"}),
    "communication_logs": ("Communication record", {"communication"}),
    "pain_assessments": ("Pain assessment", {"pain"}),
    "vital_signs_records": ("Vital-signs record", {"vitals"}),
    "wound_records": ("Wound record", {"wound", "skin", "pressure_area"}),
    "incidents": ("Incident", {"incident", "safety"}),
}


_TEXT_FIELDS: dict[str, tuple[str, ...]] = {
    "observations": ("text",),
    "sleep_records": ("quality", "night_wakings", "settled_time", "woke_time", "notes"),
    "food_intake_records": ("meal_type", "percentage_eaten"),
    "fluid_intake_records": ("volume_ml", "fluid_type"),
    "weight_records": ("weight_kg",),
    "mobility_observations": ("activity", "distance_or_duration", "assistance_given"),
    "wellbeing_records": ("mood", "notes"),
    "behaviour_records": ("behaviour_type", "behaviour_description"),
    "communication_logs": ("interaction_summary", "mood_during_interaction"),
    "pain_assessments": ("score", "location", "intervention", "scale_type", "pain_behaviours", "effective"),
    "vital_signs_records": (
        "blood_pressure_systolic", "blood_pressure_diastolic", "heart_rate_bpm", "oxygen_saturation_pct",
        "temperature_celsius", "news2_score",
    ),
    "wound_records": ("wound_type", "status", "body_location", "treatment_plan", "grade_or_category" "length_cm", "width_cm", "depth_cm"),
    "incidents": ("incident_type","immediate_action", "description", "investigation_status", "investigation_outcome"),
}

_FIELD_FORMATS = {
    "length_cm": ("Length", "cm"),
    "width_cm": ("Width", "cm"),
    "depth_cm": ("Depth", "cm"),
    "weight_kg": ("Weight", "kg"),
    "volume_ml": ("Volume", "ml"),
    "percentage_eaten": ("Amount eaten", "%"),
    "temperature_celsius": ("Temperature", "°C"),
    "heart_rate_bpm": ("Heart rate", "bpm"),
    "oxygen_saturation_pct": ("Oxygen saturation", "%"),
    "blood_pressure_systolic": ("Systolic blood pressure", "mmHg"),
    "blood_pressure_diastolic": ("Diastolic blood pressure", "mmHg"),
}

# Explicit native JSON contracts. Unknown fields never become searchable text.
_NATIVE_FIELDS = {
    "fluid_intake": ("Fluid intake", {"hydration", "nutrition", "fluid_intake"}, ("ml",)),
    "weight": ("Weight record", {"weight", "nutrition"}, ("kg",)),
    "vitals": ("Vital-signs record", {"vitals"}, (
        "systolic_bp", "diastolic_bp", "heart_rate_bpm", "spo2_pct", "temperature_c",
    )),
    "meal": ("Meal record", {"nutrition", "meal"}, ("meal", "fraction_eaten")),
    "mobility": ("Mobility observation", {"mobility", "transfer"}, (
        "activity", "distance_or_duration", "assistance_given", "text",
    )),
    "note": ("Observation note", {"observation"}, ("text",)),
}
_NATIVE_DOMAIN_TYPES = {
    EvidenceSourceType.NUTRITION: {"fluid_intake", "weight", "meal"},
    EvidenceSourceType.MOBILITY: {"mobility"},
}
_FIELD_FORMATS.update({
    "ml": ("Volume", "ml"),
    "kg": ("Weight", "kg"),
    "systolic_bp": ("Systolic blood pressure", "mmHg"),
    "diastolic_bp": ("Diastolic blood pressure", "mmHg"),
    "spo2_pct": ("Oxygen saturation", "%"),
    "temperature_c": ("Temperature", "°C"),
    "fraction_eaten": ("Fraction eaten (0–1)", None),
})


class ClinicalObservationEvidenceAdapter:
    """Maps one authorised clinical-feed source group to EvidenceDocument rows."""

    def __init__(self, session: AsyncSession, source_type: EvidenceSourceType):
        if source_type not in _SOURCES:
            raise ValueError(f"{source_type.value} is not a clinical-observation evidence source")
        self.source_type = source_type
        self._session = session
        self._reader = ObservationRepository(session)

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
        policy: PlausibilityPolicy = PlausibilityPolicy.EXCLUDE_FLAGGED,
    ) -> EvidenceRetrievalResult:
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        if from_date is not None and to_date is not None and from_date >= to_date:
            raise ValueError("from_date must be earlier than to_date")
        if current_only:
            # Observations describe what was recorded, never a standing current instruction.
            return EvidenceRetrievalResult([], 0, True, False)
        if statuses:
            raise ValueError("clinical observations do not support status filters")

        documents: list[EvidenceDocument] = []
        scanned = 0
        excluded_flagged_count: int = 0
        while scanned < MAX_SCAN_ROWS:
            page_size = min(PAGE_SIZE, MAX_SCAN_ROWS - scanned)
            rows = await self._reader.list_clinical_evidence_for_resident(
                resident_id,
                from_date=from_date,
                to_date=to_date,
                source_types=set(_SOURCES[self.source_type]),
                native_types=_NATIVE_DOMAIN_TYPES.get(self.source_type),
                limit=page_size,
                offset=scanned,
            )
            scanned += len(rows)
            exhausted = len(rows) < page_size

            for row in rows:
                if row.is_implausible:
                    continue
                row_topics = (
                    _NATIVE_FIELDS[row.type.value][1] if row.source_type == "observations"
                    else _DISPLAY[row.source_type][1]
                )
                if topics is not None and not row_topics.intersection(topics):
                    continue
                if row.is_implausible and policy == PlausibilityPolicy.EXCLUDE_FLAGGED:
                    excluded_flagged_count += 1
                    continue
                if not row.is_implausible and policy == PlausibilityPolicy.FLAGGED_ONLY:
                    continue

                documents.append(await self._document(row))
                if len(documents) == limit:
                    # Remaining rows in this page may still contain matches.
                    return EvidenceRetrievalResult(documents, scanned, False, False, excluded_flagged_count)
            if exhausted:
                return EvidenceRetrievalResult(documents, scanned, True, False, excluded_flagged_count)
        return EvidenceRetrievalResult(documents, scanned, False, True, excluded_flagged_count)

    async def get(self, *, resident_id: uuid.UUID, source_id: uuid.UUID) -> EvidenceDocument | None:
        rows = await self._reader.list_clinical_evidence_for_resident(
            resident_id,
            source_types=set(_SOURCES[self.source_type]),
            native_types=_NATIVE_DOMAIN_TYPES.get(self.source_type),
            source_id=source_id,
            limit=1,
        )
        if not rows:
            return None
        return await self._document(rows[0])

    async def _document(self, row: ObservationRead) -> EvidenceDocument:
        scope = await self._resident_scope(row.resident_id)
        if scope is None:
            raise ValueError("clinical evidence row has no active resident scope")
        care_home_id, floor_id = scope
        title, topics = _DISPLAY[row.source_type]
        fields = _TEXT_FIELDS.get(row.source_type, ())
        if row.source_type == "observations":
            title, topics, fields = _NATIVE_FIELDS[row.type.value]
        value = row.value
        source_date = date.fromisoformat(row.source_date) if row.source_date else None
        occurred_at = row.recorded_at if row.time_precision == "timestamp" else None
        return EvidenceDocument(
            evidence_id=f"{self.source_type.value}:{row.id}",
            source_type=self.source_type,
            source_id=row.id,
            resident_id=row.resident_id,
            care_home_id=care_home_id,
            floor_id=floor_id,
            authority_level=AuthorityLevel.OBSERVATION,
            topic_tags=set(topics),
            status=None,
            occurred_at=occurred_at,
            time_precision=row.time_precision,
            source_date=source_date,
            effective_from=None,
            effective_to=None,
            source_version=_revision_for(row),
            title=title,
            searchable_text=_text_for(row.source_type, title, value, fields=fields),
            structured_metadata={
                "clinical_source_type": row.source_type,
                "clinical_type": row.type.value,
                "time_precision": row.time_precision,
                "source_date": row.source_date,
                "is_implausible": row.is_implausible,
                "fields": {
                    key: None if value.get(key) is None or (
                        isinstance(value.get(key), str) and not value[key].strip()
                    ) else value[key]
                    for key in fields
                },
            },
            is_deleted=False,
            is_eligible=True,
            is_implausible=row.is_implausible,
        )

    async def _resident_scope(self, resident_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID] | None:
        row = (
            await self._session.execute(
                text(
                    "SELECT care_home_id, floor_id FROM residents "
                    "WHERE id = :resident_id AND deleted_at IS NULL AND floor_id IS NOT NULL"
                ),
                {"resident_id": resident_id},
            )
        ).mappings().one_or_none()
        return (row["care_home_id"], row["floor_id"]) if row is not None else None


def _text_for(
    source_table: str,
    title: str,
    value: dict[str, Any],
    *,
    fields: tuple[str, ...] | None = None,
) -> str:
    parts = [f"{title}."]

    for key in fields if fields is not None else _TEXT_FIELDS.get(source_table, ()):
        raw = value.get(key)
        label, unit = _FIELD_FORMATS.get(
            key,
            (key.replace("_", " ").capitalize(), None),
        )

        if raw is None or (isinstance(raw, str) and not raw.strip()):
            formatted = "Not recorded"
        elif isinstance(raw, bool):
            formatted = "Yes" if raw else "No"
        else:
            formatted = " ".join(str(raw).split())
            if unit:
                separator = "" if unit == "%" else " "
                formatted = f"{formatted}{separator}{unit}"

        parts.append(f"{label}: {formatted}.")

    return " ".join(parts)


def _revision_for(row: ObservationRead) -> str:
    """Detect a changed source even where the legacy clinical table has no updated_at."""
    canonical = json.dumps(
        {
            "id": str(row.id),
            "source_type": row.source_type,
            "type": row.type.value,
            "value": row.value,
            "recorded_at": row.recorded_at.isoformat(),
            "source_date": row.source_date,
            "created_at": row.source_updated_at.isoformat() if row.source_updated_at else None,
        },
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
