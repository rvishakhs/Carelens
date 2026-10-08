"""Versioned conservative care-event mapping. Raw strings never become safe text."""

import hashlib
import json
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from intelligence.connectors.carelens import ObservationResponse
from intelligence.core.contracts import Evidence, ExecutionContext, SourceRef


class Option(BaseModel):
    option_id: UUID
    section_id: UUID
    section_name: str
    label: str
    value_code: str | None = None
    note: str | None = None


class Measurement(BaseModel):
    measurement_id: UUID
    name: str
    unit: str | None
    value_numeric: float | None = Field(default=None, allow_inf_nan=False)
    value_text: str | None = None
    value_boolean: bool | None = None


class EventData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    template_id: UUID
    category_id: UUID
    template_name: str
    category_name: str
    status: Literal["completed", "declined", "refused", "not_applicable"]
    created_at: AwareDatetime
    updated_at: AwareDatetime
    duration_minutes: int | None = Field(default=None, ge=0)
    note: str | None = None
    summary: str | None = None
    options: list[Option]
    measurements: list[Measurement]


DRINKS = {"Drink", "Water", "Tea (drink)", "Coffee", "Juice", "Milk", "Hot Chocolate"}
MEALS = {"Breakfast", "Lunch", "Dinner", "Tea (meal)", "Supper", "Snack"}
OFFERED = {f"{n}ml": n for n in (150, 200, 280, 330, 500, 1000)}
# Exact, section-qualified choices from the current library, never substring matching.
FLAGS = {
    ("Food", "Sandwich"): "food_sandwich",
    ("Meal Size Offered", "Medium"): "meal_size_medium",
    ("Distance", "Medium Distance"): "distance_medium",
    ("Possible Trigger", "Unknown"): "trigger_unknown",
    ("Amount", "All"): "amount_all",
    ("Amount", "Half"): "amount_half",
    ("Amount Eaten", "Most"): "meal_most_eaten",
    ("Amount Eaten", "About Half"): "meal_about_half_eaten",
    ("Aid Used", "Walking Frame"): "walking_frame_used",
    ("Assistance Level", "Supervision Only"): "supervision_only",
    ("Response", "Settled"): "settled",
    ("Safety", "Remained on Premises"): "remained_on_premises",
    ("Intervention Used", "Reassurance / Distraction"): "reassurance_or_distraction",
}


def normalise_care_event(record: ObservationResponse, context: ExecutionContext) -> Evidence:
    if record.time_precision != "timestamp" or record.source_date is not None:
        raise ValueError("Care events require event timestamps")
    data = EventData.model_validate(record.value)
    kind = "note"
    if data.category_name == "Nutrition & Hydration":
        if data.template_name in DRINKS:
            kind = "fluid_intake"
        elif data.template_name in MEALS:
            kind = "meal"
    elif data.category_name == "Mobility":
        kind = "mobility"
    elif data.category_name == "Emotional Support & Behaviour":
        kind = "behaviour" if data.template_name == "Wandering" else "wellbeing"

    # Raw data is internal evidence only. Renderer uses a separate allowlist.
    clinical = {"raw_care_event": record.value, "mapping_version": "care-events-v2"}
    clinical[f"status_{data.status}"] = True
    clinical["duration_minutes"] = data.duration_minutes
    clinical["is_wandering"] = data.template_name == "Wandering"
    clinical["is_walk"] = data.template_name == "Walk"
    if kind == "fluid_intake" and data.template_name == "Tea (drink)":
        clinical["drink_tea"] = True
    # Exact whole-note vocabulary only: never substring-match or forward raw notes.
    # Additional context (including a name, negation or injury) prevents this mapping.
    if kind == "behaviour" and (data.note or "").strip().rstrip(".").casefold() in {
        "was wandering around the garden", "wandering in the garden",
    }:
        clinical["wandering_in_garden"] = True
    for option in data.options:
        flag = FLAGS.get((option.section_name, option.label))
        if flag:
            clinical[flag] = True

    # Offered quantity is explicit; consumed quantity is only an estimate from choices.
    # Do not populate consumed_ml: exact recorded metrics must remain unknown.
    offered = [o for o in data.options if o.section_name == "Quantity Offered"]
    amount = [o for o in data.options if o.section_name == "Amount"]
    if kind == "fluid_intake" and data.status == "completed" and len(offered) == 1:
        quantity = OFFERED.get(offered[0].value_code or offered[0].label)
        if quantity is not None:
            clinical["offered_ml"] = quantity
            if len(amount) == 1 and amount[0].label in {"All", "Half"}:
                clinical["estimated_consumed_ml"] = quantity * (1 if amount[0].label == "All" else 0.5)

    fingerprint = hashlib.sha256(
        json.dumps(
            record.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    return Evidence(
        tenant_id=context.tenant_id,
        resident_id=record.resident_id,
        reference=SourceRef(
            source_system="Carelens_connector",
            source_type="care_events",
            source_id=record.id,
            version=data.updated_at.isoformat(),
            fingerprint=fingerprint,
        ),
        effective_at=record.recorded_at,
        recorded_at=data.created_at,
        time_basis="effective",
        time_precision="timestamp",
        kind=kind,
        clinical_data=clinical,
        is_implausible=record.is_implausible,
    )
