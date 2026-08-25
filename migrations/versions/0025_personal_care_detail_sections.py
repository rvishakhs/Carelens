"""Personal Care: task-specific detail sections for every template

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-25

Every Personal Care template previously carried nothing but a generic "Outcome"
(Completed Independently/with Assistance/Partially Completed/Declined/Refused) or
"Result" (OK/Needs Attention/Actioned) section -- true of the task, but capturing
none of what actually happened. This adds a task-specific detail section (or two)
above that generic outcome for every template, modelled on real UK care-home
documentation practice (oral hygiene and hearing-aid care option sets in particular
follow standard care-charting categories: brushing/mouthwash/mouth-swab technique
and mouth-condition flags; hearing-aid insertion/removal/cleaning/battery actions by
ear). Clinically significant findings are flagged with triggers_alert=true, the same
convention the seeded library already uses (e.g. Nutrition's "Refused").
"""
import uuid
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# template_name -> list of (section_name, allow_multiple, [option_labels])
SECTIONS_TO_ADD: dict[str, list[tuple[str, bool, list[str]]]] = {
    "Wash": [
        ("Areas Washed", True, ["Face", "Hands", "Upper Body", "Lower Body", "Back", "Full Body", "Perineal Area"]),
    ],
    "Dress": [
        ("Dress Type", False, ["Day Wear", "Night Wear", "Just Changing Clothes"]),
    ],
    "Change Clothes": [
        ("Reason", False, ["Soiled", "Wet", "Spillage", "Personal Preference", "Scheduled Change"]),
    ],
    "Bath": [
        ("Bath Type", False, ["Full Bath", "Bed Bath", "Strip Wash", "Assisted Bath"]),
        ("Skin Condition", True, ["Normal", "Redness", "Broken Skin", "Bruising", "Rash", "Dry Skin", "Pressure Area"]),
    ],
    "Shower": [
        ("Shower Type", False, ["Standing Shower", "Shower Chair", "Assisted Shower"]),
        ("Skin Condition", True, ["Normal", "Redness", "Broken Skin", "Bruising", "Rash", "Dry Skin", "Pressure Area"]),
    ],
    "Denture Care": [
        ("Care Given", True, ["Removed", "Cleaned", "Soaked Overnight", "Fixative Applied", "Replaced", "Mouth Rinsed"]),
        ("Denture Condition", False, ["Good Fit", "Loose / Ill-fitting", "Damaged", "Missing"]),
    ],
    "Oral Hygiene": [
        ("Care Provided", True, ["Teeth Brushed", "Mouthwash Used", "Mouth Swabbed", "Lips Moisturized", "Denture Care Given"]),
        ("Mouth Condition", True, ["Normal", "Dry", "Ulcers / Sores", "Bleeding Gums", "Coating / Thrush", "Bad Breath"]),
    ],
    "Wash Hands": [
        ("When", False, ["Before Meal", "After Meal", "After Toilet", "General"]),
    ],
    "Wash Hair": [
        ("Method", False, ["Shampoo at Basin", "In Shower", "In Bath", "Dry Shampoo", "Hairdresser Visit"]),
    ],
    "Brush Hair": [
        ("Styled", False, ["Yes", "No"]),
    ],
    "Catheter Care": [
        ("Care Given", True, ["Bag Emptied", "Bag Changed", "Site Cleaned", "Catheter Secured / Repositioned"]),
        ("Urine Appearance", False, ["Clear", "Cloudy", "Blood-stained", "Dark / Concentrated", "Sediment Present", "Offensive Odour"]),
    ],
    "Make-up": [
        ("Areas", True, ["Face", "Eyes", "Lips"]),
    ],
    "Shave": [
        ("Method", False, ["Wet Shave", "Electric Razor", "Beard Trim Only"]),
        ("Skin Check", True, ["No Issues", "Nicks / Cuts", "Redness / Irritation"]),
    ],
    "Menstruation": [
        ("Products Used", True, ["Pad", "Tampon", "Period Pants", "Liner"]),
        ("Flow / Condition", False, ["Light", "Moderate", "Heavy", "Clots Noted", "Pain / Discomfort Reported"]),
    ],
    "Cleaning": [
        ("Item / Area Cleaned", True, ["Room", "Personal Items", "Glasses", "Hearing Aid Case", "Mobility Aid", "Other"]),
    ],
    "Check Finger Nails": [
        ("Nail Condition", True, ["Trimmed", "Clean", "Discoloured", "Ingrown", "Fungal Infection Signs", "Referral Needed"]),
    ],
    "Hairdresser": [
        ("Service", True, ["Haircut", "Wash & Set", "Colour", "Trim", "Style"]),
    ],
    "Chiropodist": [
        ("Treatment Given", True, ["Nail Trim", "Corn Removal", "Callus Treatment", "Diabetic Foot Check", "Referral Made"]),
    ],
    "Check Toe Nails": [
        ("Nail Condition", True, ["Trimmed", "Clean", "Discoloured", "Ingrown", "Fungal Infection Signs", "Corns / Calluses Noted", "Referral Needed"]),
    ],
    "Check Glasses": [
        ("Condition", True, ["Clean", "Scratched Lens", "Damaged Frame", "Missing", "Prescription Check Due"]),
    ],
    "Check Ears": [
        ("Findings", True, ["Clean", "Wax Build-up", "Discharge", "Redness / Infection Signs", "Pain Reported"]),
    ],
    "Hearing Aid": [
        ("Action Taken", True, ["Inserted", "Removed", "Cleaned", "Battery Changed", "Battery Checked"]),
        ("Ear(s)", False, ["Left", "Right", "Both"]),
    ],
    "Check Eye": [
        ("Findings", True, ["Clear", "Redness", "Discharge", "Swelling", "Cataract Signs", "Vision Complaint"]),
    ],
    "Laundry": [
        ("Type", True, ["Personal Clothing", "Bedding", "Towels"]),
    ],
}

# Templates with no section at all today -- get the standard Outcome scale appended
# after their new detail section(s), same options every other task-outcome uses.
NEEDS_NEW_OUTCOME = ["Wash Hands", "Brush Hair", "Make-up", "Cleaning", "Hairdresser", "Chiropodist", "Laundry"]
STANDARD_OUTCOME_OPTIONS = ["Completed Independently", "Completed with Assistance", "Partially Completed", "Declined", "Refused"]

# Exact option labels that represent a clinically-significant finding worth flagging,
# mirroring how the seeded library already flags e.g. Nutrition's "Refused".
ALERT_LABELS = {
    "Broken Skin", "Pressure Area", "Damaged", "Missing",
    "Ulcers / Sores", "Bleeding Gums", "Coating / Thrush",
    "Blood-stained", "Sediment Present", "Offensive Odour",
    "Nicks / Cuts", "Redness / Irritation",
    "Heavy", "Clots Noted", "Pain / Discomfort Reported",
    "Discoloured", "Ingrown", "Fungal Infection Signs", "Referral Needed", "Corns / Calluses Noted",
    "Scratched Lens", "Damaged Frame",
    "Discharge", "Redness / Infection Signs", "Pain Reported",
    "Swelling", "Vision Complaint",
}


def _slug(label: str) -> str:
    return label.lower().replace(" / ", "_").replace(" & ", "_").replace(" ", "_").replace("(", "").replace(")", "")


def _template_lookup(bind, name: str):
    return bind.execute(
        text(
            "select t.id, t.care_home_id from care_templates t "
            "join care_categories c on c.id = t.category_id "
            "where c.name = 'Personal Care' and t.name = :name"
        ),
        {"name": name},
    ).first()


def upgrade() -> None:
    bind = op.get_bind()

    for template_name, sections in SECTIONS_TO_ADD.items():
        row = _template_lookup(bind, template_name)
        if row is None:
            continue
        template_id, care_home_id = row.id, row.care_home_id

        existing = bind.execute(
            text("select id from care_template_sections where template_id = :tid order by sort_order limit 1"),
            {"tid": template_id},
        ).first()
        if existing is not None:
            bind.execute(
                text("update care_template_sections set sort_order = :so where id = :id"),
                {"so": len(sections) + 1, "id": existing.id},
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

    for template_name in NEEDS_NEW_OUTCOME:
        row = _template_lookup(bind, template_name)
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
        row = _template_lookup(bind, template_name)
        if row is None:
            continue
        template_id = row.id
        added_section_names = [name for name, _, _ in SECTIONS_TO_ADD.get(template_name, [])]
        if template_name in NEEDS_NEW_OUTCOME:
            added_section_names.append("Outcome")

        section_rows = bind.execute(
            text("select id, name from care_template_sections where template_id = :tid and name = any(:names)"),
            {"tid": template_id, "names": added_section_names},
        ).all()
        section_ids = [r.id for r in section_rows]
        if section_ids:
            bind.execute(text("delete from care_template_options where section_id = any(:ids)"), {"ids": section_ids})
            bind.execute(text("delete from care_template_sections where id = any(:ids)"), {"ids": section_ids})

        # restore the original first-section sort_order (whatever's left, lowest wins)
        remaining = bind.execute(
            text("select id from care_template_sections where template_id = :tid order by sort_order limit 1"), {"tid": template_id}
        ).first()
        if remaining is not None:
            bind.execute(text("update care_template_sections set sort_order = 1 where id = :id"), {"id": remaining.id})
