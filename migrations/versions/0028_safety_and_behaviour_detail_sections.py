"""Personal Safety & Environment + Emotional Support & Behaviour: detail sections

Revision ID: 0028
Revises: 0027
Create Date: 2026-08-25

Same treatment as 0025 (Personal Care) and 0026 (Toileting/Mobility).

Emotional Support & Behaviour is modelled on standard BPSD (behavioural and
psychological symptoms of dementia) charting practice -- NICE/Alzheimer's Society
guidance on managing behaviours that challenge centres on identifying a *trigger*
before reaching for medication, trying a non-drug *intervention* first, and
recording the *response*, so every specific-behaviour template gets that
Trigger -> Intervention -> Response triad. Wandering additionally gets a Safety
section, since exit-seeking/elopement risk is a distinct, separately-tracked
safety concern from the behaviour itself.

Personal Safety & Environment's equipment/room checks previously only recorded
"OK / Needs Attention / Actioned" with no detail on *what* was checked or found --
enriched using real safety-critical categories for this equipment: bed rail
entrapment-risk assessment (an MHRA/CQC safety focus), hoist sling condition,
wheelchair/chair mechanical checks, footwear falls-prevention assessment (a NICE
falls-guidance measure), and pendant-alarm functional checks. Unlike the earlier
categories, these are staff-side environment/equipment checks rather than tasks
performed on/with the resident, so no generic Outcome section is added here --
it wouldn't mean anything for "Check Bedrails".
"""
import uuid
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CATEGORIES = ("Emotional Support & Behaviour", "Personal Safety & Environment")

BEHAVIOUR_TEMPLATES = [
    "Agitated", "Confused", "Pacing", "Upset", "Distressed",
    "Repetitive Behaviour", "Paranoid", "Hallucinating", "Disinhibited", "Wandering",
]
TRIGGER_INTERVENTION_RESPONSE: list[tuple[str, bool, list[str]]] = [
    ("Possible Trigger", True, [
        "Pain", "Hunger / Thirst", "Unfamiliar Environment", "Overstimulation / Noise",
        "Time of Day (Sundowning)", "Medical Issue Suspected", "Unknown", "Other",
    ]),
    ("Intervention Used", True, [
        "Reassurance / Distraction", "Redirected to Activity", "Quiet Space Offered",
        "1:1 Support Given", "Family / Familiar Person Involved", "Environment Adjusted", "PRN Medication Given",
    ]),
    ("Response", False, ["Settled", "Partially Settled", "No Change", "Escalated"]),
]

# template_name -> list of (section_name, allow_multiple, [option_labels])
SECTIONS_TO_ADD: dict[str, list[tuple[str, bool, list[str]]]] = {
    **{name: list(TRIGGER_INTERVENTION_RESPONSE) for name in BEHAVIOUR_TEMPLATES},
    "Wandering": [
        *TRIGGER_INTERVENTION_RESPONSE,
        ("Safety", False, ["Remained on Premises", "Attempted to Leave", "Exit-Seeking Behaviour", "Found Outside"]),
    ],
    "Social Worker Involved": [
        ("Reason for Involvement", False, [
            "Safeguarding Concern", "Best Interests Meeting", "Care Review",
            "Family Liaison", "Mental Capacity Assessment", "Other",
        ]),
    ],
    "Emotional Support Given": [
        ("Support Type", True, [
            "Active Listening", "Reassurance", "Reminiscence",
            "Companionship", "Spiritual / Religious Support", "Family Contact Facilitated",
        ]),
    ],
    "Fridge Temperature": [
        ("Fridge Type", False, ["Medication Fridge", "Food Fridge", "Communal Kitchen Fridge"]),
    ],
    "Check OK (Wellbeing)": [
        ("Observed", True, ["Comfortable", "Settled", "Awake", "Asleep", "In Pain", "Distressed"]),
    ],
    "Change Bed": [
        ("Reason", False, ["Scheduled Change", "Soiled", "Wet", "Spillage", "Resident Request"]),
        ("Items Changed", True, ["Sheets", "Pillowcases", "Duvet Cover", "Mattress Protector"]),
    ],
    "Check Mattress": [
        ("Mattress Type", False, ["Standard", "Pressure Relief - Foam", "Pressure Relief - Alternating Air", "Profiling Bed"]),
        ("Condition", True, ["Clean", "Functioning Correctly", "Stained", "Damaged", "Motor / Pump Fault"]),
    ],
    "Check Bedrails": [
        ("Findings", True, ["Secure & Correct Height", "Gap / Entrapment Risk Identified", "Padding Damaged", "Loose Fitting"]),
    ],
    "Check Chair": [
        ("Condition", True, ["Stable & Secure", "Wheels Not Locking", "Cushion Damaged", "Armrest Loose", "Needs Cleaning"]),
    ],
    "Action Mat": [
        ("Position", False, ["Beside Bed", "Both Sides", "Removed"]),
        ("Condition", False, ["Good Condition", "Needs Replacement", "Not in Use"]),
    ],
    "Check Wheelchair": [
        ("Condition Check", True, ["Brakes Working", "Brakes Faulty", "Tyres / Wheels OK", "Footplates Loose", "Cushion Soiled", "Frame Damaged"]),
    ],
    "Wheelchair Belt": [
        ("Status", False, ["Fitted & Secure", "Not Required", "Declined by Resident", "Missing / Damaged"]),
    ],
    "Check Sling": [
        ("Findings", True, ["Correct Size & Good Condition", "Fraying / Damage Noted", "Straps Worn", "Label / Weight Limit Illegible"]),
    ],
    "Adjust Curtains": [
        ("Action", False, ["Opened", "Closed", "Partially Closed"]),
        ("Reason", False, ["Daytime", "Privacy", "Sunlight / Glare", "Bedtime"]),
    ],
    "Check Room": [
        ("Issues Found", True, [
            "None", "Clutter / Trip Hazard", "Call Bell Not Reachable",
            "Poor Lighting", "Flooring Hazard", "Temperature Issue", "Personal Items Inaccessible",
        ]),
    ],
    "Room Temperature": [
        ("Status", False, ["Comfortable", "Too Cold", "Too Warm"]),
    ],
    "Check Footwear": [
        ("Condition", True, ["Correct Fit & Non-Slip", "Fastened Securely", "Worn / Damaged Sole", "Poor Fit", "Not Wearing Appropriate Footwear"]),
    ],
    "Check Equipment": [
        ("Equipment Type", False, ["Hoist", "Wheelchair", "Walking Frame", "Profiling Bed", "Pressure Mattress", "Call Bell", "Other"]),
        ("Condition", False, ["Working Correctly", "Needs Repair", "Out of Service", "Missing"]),
    ],
    "Pendant Alarm Check": [
        ("Check Result", True, ["Battery OK", "Signal OK", "Worn Correctly", "Battery Low", "Not Responding", "Not Worn"]),
    ],
}

ALERT_LABELS = {
    "Escalated",
    "Attempted to Leave", "Exit-Seeking Behaviour", "Found Outside",
    "Stained", "Damaged", "Motor / Pump Fault",
    "Gap / Entrapment Risk Identified", "Padding Damaged", "Loose Fitting",
    "Wheels Not Locking", "Cushion Damaged", "Armrest Loose",
    "Needs Replacement",
    "Brakes Faulty", "Footplates Loose", "Cushion Soiled", "Frame Damaged",
    "Missing / Damaged",
    "Fraying / Damage Noted", "Straps Worn", "Label / Weight Limit Illegible",
    "Clutter / Trip Hazard", "Call Bell Not Reachable", "Poor Lighting", "Flooring Hazard", "Temperature Issue", "Personal Items Inaccessible",
    "Too Cold", "Too Warm",
    "Worn / Damaged Sole", "Poor Fit", "Not Wearing Appropriate Footwear",
    "Needs Repair", "Out of Service", "Missing",
    "Battery Low", "Not Responding", "Not Worn",
    "In Pain", "Distressed",
}


def _slug(label: str) -> str:
    return label.lower().replace(" / ", "_").replace(" (", "_").replace(")", "").replace(":", "").replace(" ", "_")


def _find_template(bind, name: str):
    for category in CATEGORIES:
        row = bind.execute(
            text(
                "select t.id, t.care_home_id from care_templates t "
                "join care_categories c on c.id = t.category_id "
                "where c.name = :category and t.name = :name"
            ),
            {"category": category, "name": name},
        ).first()
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


def downgrade() -> None:
    bind = op.get_bind()

    for template_name, sections in SECTIONS_TO_ADD.items():
        row = _find_template(bind, template_name)
        if row is None:
            continue
        template_id = row.id
        added_section_names = [name for name, _, _ in sections]

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
