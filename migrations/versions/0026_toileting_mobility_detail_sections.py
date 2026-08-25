"""Toileting & Mobility: task-specific detail sections for every template

Revision ID: 0026
Revises: 0025
Create Date: 2026-08-25

Same treatment as 0025's Personal Care pass: every Toileting/Mobility template only
carried a generic Outcome/Result/Assistance Level scale, capturing that a task
happened but nothing about what was actually found or done. Modelled on real UK
care-home charting practice -- continence charts (pad status + skin integrity),
bowel charts (colour/consistency alongside the existing Bristol Stool Type),
moving-and-handling equipment logs, pressure-area repositioning charts, and
post-fall protocol (location/witnessed/injury/actions taken, the most heavily
audited incident type in elderly care). Clinically significant findings are
flagged with triggers_alert, matching the seeded library's existing convention.

Unlike 0025 (where every template had at most one pre-existing section), a couple
of these templates already carry two (e.g. Bowels Opened: Outcome + Bristol Stool
Type), so this generalises the previous migration's "bump the first section" step
into "bump every existing section", preserving their relative order.
"""
import uuid
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CATEGORIES = ("Toileting", "Mobility")

# template_name -> list of (section_name, allow_multiple, [option_labels])
SECTIONS_TO_ADD: dict[str, list[tuple[str, bool, list[str]]]] = {
    # -- Toileting --
    "Toilet Help": [
        ("Assistance Given", True, ["Transferred to Toilet", "Clothing Adjusted", "Hygiene Assistance", "Hand Washing Assisted"]),
    ],
    "Urine Bottle": [
        ("Amount", False, ["Small", "Moderate", "Large", "Empty / None"]),
        ("Urine Appearance", False, ["Clear", "Cloudy", "Blood-stained", "Dark / Concentrated", "Sediment Present", "Offensive Odour"]),
    ],
    "Bed Pan": [
        ("Amount", False, ["Small", "Moderate", "Large", "Empty / None"]),
        ("Urine Appearance", False, ["Clear", "Cloudy", "Blood-stained", "Dark / Concentrated", "Sediment Present", "Offensive Odour"]),
    ],
    "Commode": [
        ("Output Type", True, ["Urine", "Stool"]),
        ("Amount", False, ["Small", "Moderate", "Large"]),
    ],
    "Pad Check": [
        ("Pad Status", False, ["Dry", "Damp", "Wet", "Soaked", "Soiled (Faeces)"]),
        ("Skin Check", True, ["Normal", "Redness", "Broken Skin", "Rash", "Pressure Area"]),
    ],
    "Urinate": [
        ("Urine Appearance", False, ["Clear", "Cloudy", "Blood-stained", "Dark / Concentrated", "Sediment Present", "Offensive Odour"]),
    ],
    "Bowels Opened": [
        ("Colour", False, ["Normal / Brown", "Pale / Clay-coloured", "Black / Tarry", "Red / Bloody", "Green"]),
        ("Amount", False, ["Small", "Moderate", "Large"]),
    ],
    "Loose Bowels": [
        ("Bristol Stool Type", False, ["Type 1", "Type 2", "Type 3", "Type 4", "Type 5", "Type 6", "Type 7"]),
        ("Associated Symptoms", True, ["None", "Abdominal Pain", "Cramping", "Urgency", "Blood Noted", "Mucus Noted"]),
    ],
    "Emptied": [
        ("Item Emptied", False, ["Catheter Bag", "Commode Pot", "Urine Bottle", "Bed Pan"]),
    ],
    "Wet Clothes": [
        ("Extent", False, ["Slightly Damp", "Wet", "Soaked"]),
        ("Action Taken", True, ["Clothes Changed", "Bedding Changed", "Skin Checked", "Skin Cream Applied"]),
    ],
    "Soiled Clothes": [
        ("Extent", False, ["Small Amount", "Moderate", "Heavily Soiled"]),
        ("Action Taken", True, ["Clothes Changed", "Bedding Changed", "Skin Cleaned", "Barrier Cream Applied"]),
    ],
    # -- Mobility --
    "Onto Chair": [
        ("Equipment Used", True, ["None", "Walking Frame", "Wheelchair", "Standing Aid", "Slide Sheet", "Transfer Board"]),
    ],
    "Up From Chair": [
        ("Equipment Used", True, ["None", "Walking Frame", "Wheelchair", "Standing Aid", "Slide Sheet", "Transfer Board"]),
    ],
    "Into Bed": [
        ("Equipment Used", True, ["None", "Bed Rail", "Slide Sheet", "Hoist", "Standing Aid", "Transfer Board"]),
    ],
    "Out of Bed": [
        ("Equipment Used", True, ["None", "Bed Rail", "Slide Sheet", "Hoist", "Standing Aid", "Transfer Board"]),
    ],
    "Hoist (2 People)": [
        ("Sling Type", False, ["Full Body Sling", "Toileting Sling", "Standing Sling", "Amputee Sling"]),
    ],
    "Standing Hoist": [
        ("Sling Type", False, ["Standing Sling", "Walking Belt / Harness"]),
    ],
    "Handling Belt": [
        ("Purpose", False, ["Transfer", "Walking Support", "Repositioning"]),
    ],
    "Elevate Legs": [
        ("Reason", False, ["Swelling / Oedema", "Circulation", "Comfort", "Post-Fall", "Care Plan Requirement"]),
    ],
    "Moved": [
        ("Position", False, ["Left Side", "Right Side", "Back", "Sitting Up", "Standing"]),
    ],
    "Walk": [
        ("Aid Used", True, ["None", "Walking Stick", "Walking Frame", "Rollator", "One Carer Support", "Two Carer Support"]),
        ("Distance", False, ["Short Distance (<5m)", "Medium Distance", "Long Distance", "Full Lap / Corridor"]),
    ],
    "Stairs": [
        ("Direction", False, ["Up", "Down", "Both"]),
        ("Aid Used", True, ["Handrail", "Stair Lift", "One Carer Support", "Two Carer Support"]),
    ],
    "Turn (Repositioned)": [
        ("Position", False, ["Left Side", "Right Side", "Back", "Prone", "Sitting Up"]),
        ("Skin Check", True, ["Normal", "Redness", "Broken Skin", "Pressure Area", "Bruising"]),
    ],
    "Fall": [
        ("Location", False, ["Bedroom", "Bathroom", "Corridor", "Dining Room", "Lounge", "Outdoors", "Other"]),
        ("Witnessed", False, ["Witnessed", "Unwitnessed / Found on Floor", "Reported by Resident"]),
        ("Injury", True, ["None", "Bruising", "Skin Tear", "Laceration", "Suspected Fracture", "Head Injury", "Pain Reported"]),
        ("Actions Taken", True, [
            "Neurological Observations Started", "GP Called", "Ambulance Called",
            "Family Informed", "Incident Report Completed", "Assisted Back to Bed / Chair",
        ]),
    ],
}

# Measurements to add alongside sections, for templates where a number matters.
MEASUREMENTS_TO_ADD: dict[str, list[tuple[str, str, str | None, bool]]] = {
    # (name, data_type, unit, is_required)
    "Emptied": [("Volume", "numeric", "ml", False)],
    "Elevate Legs": [("Duration", "numeric", "min", False)],
}

# Templates with no section at all today -- get the standard Outcome scale appended
# after their new detail section(s). Fall is deliberately excluded: "Completed
# Independently / Declined" doesn't describe an incident.
NEEDS_NEW_OUTCOME = ["Loose Bowels", "Emptied", "Wet Clothes", "Soiled Clothes", "Elevate Legs", "Turn (Repositioned)"]
STANDARD_OUTCOME_OPTIONS = ["Completed Independently", "Completed with Assistance", "Partially Completed", "Declined", "Refused"]

ALERT_LABELS = {
    "Soaked", "Soiled (Faeces)", "Heavily Soiled",
    "Redness", "Broken Skin", "Pressure Area", "Rash", "Bruising",
    "Blood-stained", "Sediment Present", "Offensive Odour", "Dark / Concentrated", "Cloudy",
    "Black / Tarry", "Red / Bloody", "Pale / Clay-coloured", "Green",
    "Blood Noted", "Abdominal Pain",
    "Skin Tear", "Laceration", "Suspected Fracture", "Head Injury", "Pain Reported",
    "Unwitnessed / Found on Floor",
}


def _slug(label: str) -> str:
    return label.lower().replace(" / ", "_").replace(" (", "_").replace(")", "").replace(" ", "_")


def _template_lookup(bind, category: str, name: str):
    return bind.execute(
        text(
            "select t.id, t.care_home_id from care_templates t "
            "join care_categories c on c.id = t.category_id "
            "where c.name = :category and t.name = :name"
        ),
        {"category": category, "name": name},
    ).first()


def _find_template(bind, name: str):
    for category in CATEGORIES:
        row = _template_lookup(bind, category, name)
        if row is not None:
            return row
    return None


def upgrade() -> None:
    bind = op.get_bind()

    for template_name, sections in SECTIONS_TO_ADD.items():
        row = _find_template(bind, template_name)
        if row is None:
            continue
        template_id, care_home_id = row.id, row.care_home_id

        # Bump every pre-existing section (not just the first -- Bowels Opened
        # already has two: Outcome and Bristol Stool Type) to make room, preserving
        # their relative order.
        existing_sections = bind.execute(
            text("select id from care_template_sections where template_id = :tid order by sort_order"), {"tid": template_id}
        ).all()
        for offset, existing in enumerate(existing_sections):
            bind.execute(
                text("update care_template_sections set sort_order = :so where id = :id"),
                {"so": len(sections) + offset + 1, "id": existing.id},
            )

        for i, (section_name, allow_multiple, options) in enumerate(sections, start=1):
            section_id = uuid.uuid4()
            bind.execute(
                text(
                    "insert into care_template_sections (id, care_home_id, template_id, name, sort_order, allow_multiple, is_active) "
                    "values (:id, :chid, :tid, :name, :so, :multi, true)"
                ),
                {"id": section_id, "chid": care_home_id, "tid": template_id, "name": section_name, "so": i, "multi": allow_multiple},
            )
            for j, label in enumerate(options, start=1):
                bind.execute(
                    text(
                        "insert into care_template_options "
                        "(id, care_home_id, section_id, label, value_code, sort_order, requires_note, triggers_alert, is_active) "
                        "values (:id, :chid, :sid, :label, :code, :so, false, :alert, true)"
                    ),
                    {
                        "id": uuid.uuid4(),
                        "chid": care_home_id,
                        "sid": section_id,
                        "label": label,
                        "code": _slug(label),
                        "so": j,
                        "alert": label in ALERT_LABELS,
                    },
                )

    for template_name, measurements in MEASUREMENTS_TO_ADD.items():
        row = _find_template(bind, template_name)
        if row is None:
            continue
        template_id, care_home_id = row.id, row.care_home_id
        for name, data_type, unit, is_required in measurements:
            bind.execute(
                text(
                    "insert into care_template_measurements (id, care_home_id, template_id, name, data_type, unit, is_required, sort_order) "
                    "values (:id, :chid, :tid, :name, :dtype, :unit, :req, 0)"
                ),
                {"id": uuid.uuid4(), "chid": care_home_id, "tid": template_id, "name": name, "dtype": data_type, "unit": unit, "req": is_required},
            )

    for template_name in NEEDS_NEW_OUTCOME:
        row = _find_template(bind, template_name)
        if row is None:
            continue
        template_id, care_home_id = row.id, row.care_home_id
        max_so = bind.execute(
            text("select coalesce(max(sort_order), 0) from care_template_sections where template_id = :tid"), {"tid": template_id}
        ).scalar()
        section_id = uuid.uuid4()
        bind.execute(
            text(
                "insert into care_template_sections (id, care_home_id, template_id, name, sort_order, allow_multiple, is_active) "
                "values (:id, :chid, :tid, 'Outcome', :so, false, true)"
            ),
            {"id": section_id, "chid": care_home_id, "tid": template_id, "so": max_so + 1},
        )
        for j, label in enumerate(STANDARD_OUTCOME_OPTIONS, start=1):
            bind.execute(
                text(
                    "insert into care_template_options "
                    "(id, care_home_id, section_id, label, value_code, sort_order, requires_note, triggers_alert, is_active) "
                    "values (:id, :chid, :sid, :label, :code, :so, false, false, true)"
                ),
                {"id": uuid.uuid4(), "chid": care_home_id, "sid": section_id, "label": label, "code": _slug(label), "so": j},
            )


def downgrade() -> None:
    bind = op.get_bind()

    for template_name in list(SECTIONS_TO_ADD.keys()) + NEEDS_NEW_OUTCOME:
        row = _find_template(bind, template_name)
        if row is None:
            continue
        template_id = row.id
        added_section_names = [name for name, _, _ in SECTIONS_TO_ADD.get(template_name, [])]
        if template_name in NEEDS_NEW_OUTCOME:
            added_section_names.append("Outcome")

        section_rows = bind.execute(
            text("select id from care_template_sections where template_id = :tid and name = any(:names)"),
            {"tid": template_id, "names": added_section_names},
        ).all()
        section_ids = [r.id for r in section_rows]
        if section_ids:
            bind.execute(text("delete from care_template_options where section_id = any(:ids)"), {"ids": section_ids})
            bind.execute(text("delete from care_template_sections where id = any(:ids)"), {"ids": section_ids})

        remaining = bind.execute(
            text("select id from care_template_sections where template_id = :tid order by sort_order"), {"tid": template_id}
        ).all()
        for i, r in enumerate(remaining, start=1):
            bind.execute(text("update care_template_sections set sort_order = :so where id = :id"), {"so": i, "id": r.id})

    for template_name, measurements in MEASUREMENTS_TO_ADD.items():
        row = _find_template(bind, template_name)
        if row is None:
            continue
        for name, *_ in measurements:
            bind.execute(
                text("delete from care_template_measurements where template_id = :tid and name = :name"),
                {"tid": row.id, "name": name},
            )
