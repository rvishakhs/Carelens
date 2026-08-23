"""Nutrition & Hydration: meal size offered + drink quantity offered

Revision ID: 0024
Revises: 0023
Create Date: 2026-08-23

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The 10 templates that follow the Food -> Amount Eaten -> Percentage Eaten pattern
# (the 5 named meals plus the standalone food-item snacks that share the same shape).
MEAL_PATTERN_TEMPLATES = [
    "Breakfast", "Lunch", "Tea (meal)", "Snack", "Supper",
    "Soup", "Pudding", "Jelly", "Ice Lolly", "Ice Cream",
]

# Every Amount -> Volume(ml) drink template in the category.
DRINK_PATTERN_TEMPLATES = [
    "Jelly Drops", "Soft Drink", "Tea (drink)", "Coffee", "Hot Chocolate", "Drink",
    "Water", "Juice", "Milk", "Milkshake", "Thick Drink", "Ensure", "Wine", "Alcoholic Drink",
]


def upgrade() -> None:
    # "Percentage Eaten" was a free-number guess at how much was eaten; "Meal Size
    # Offered" (Small/Medium/Large) captures the actually-useful, quick-tap fact --
    # how big a portion was given in the first place -- so it goes where the number
    # entry used to be, directly above "Amount Eaten" (which already covers how much
    # of *that* portion was consumed).
    op.execute(f"""
DO $$
DECLARE
  tpl RECORD;
  new_section_id uuid;
BEGIN
  FOR tpl IN
    SELECT t.id, t.care_home_id
    FROM care_templates t
    JOIN care_categories c ON c.id = t.category_id
    WHERE c.name = 'Nutrition & Hydration'
      AND t.name IN ({",".join(f"'{n}'" for n in MEAL_PATTERN_TEMPLATES)})
  LOOP
    -- Drop any already-recorded "Percentage Eaten" values before removing the
    -- measurement definition (FK-blocked otherwise) -- fine at this stage since
    -- the only rows that exist are pre-launch test data, not real resident history.
    DELETE FROM care_event_measurements WHERE care_template_measurement_id IN (
      SELECT id FROM care_template_measurements WHERE template_id = tpl.id AND name = 'Percentage Eaten'
    );
    DELETE FROM care_template_measurements WHERE template_id = tpl.id AND name = 'Percentage Eaten';

    UPDATE care_template_sections SET sort_order = 3 WHERE template_id = tpl.id AND name = 'Amount Eaten';

    INSERT INTO care_template_sections (id, care_home_id, template_id, name, sort_order, allow_multiple, is_active)
    VALUES (gen_random_uuid(), tpl.care_home_id, tpl.id, 'Meal Size Offered', 2, false, true)
    RETURNING id INTO new_section_id;

    INSERT INTO care_template_options (id, care_home_id, section_id, label, value_code, sort_order, requires_note, triggers_alert, is_active)
    VALUES
      (gen_random_uuid(), tpl.care_home_id, new_section_id, 'Small', 'small', 1, false, false, true),
      (gen_random_uuid(), tpl.care_home_id, new_section_id, 'Medium', 'medium', 2, false, false, true),
      (gen_random_uuid(), tpl.care_home_id, new_section_id, 'Large', 'large', 3, false, false, true);
  END LOOP;
END $$;
""")

    # "Quantity Offered" mirrors the same idea for drinks -- the standard vessel/serve
    # sizes actually used on the ward, offered before "Amount" (how much was drunk).
    op.execute(f"""
DO $$
DECLARE
  tpl RECORD;
  new_section_id uuid;
BEGIN
  FOR tpl IN
    SELECT t.id, t.care_home_id
    FROM care_templates t
    JOIN care_categories c ON c.id = t.category_id
    WHERE c.name = 'Nutrition & Hydration'
      AND t.name IN ({",".join(f"'{n}'" for n in DRINK_PATTERN_TEMPLATES)})
  LOOP
    UPDATE care_template_sections SET sort_order = 2 WHERE template_id = tpl.id AND name = 'Amount';

    INSERT INTO care_template_sections (id, care_home_id, template_id, name, sort_order, allow_multiple, is_active)
    VALUES (gen_random_uuid(), tpl.care_home_id, tpl.id, 'Quantity Offered', 1, false, true)
    RETURNING id INTO new_section_id;

    INSERT INTO care_template_options (id, care_home_id, section_id, label, value_code, sort_order, requires_note, triggers_alert, is_active)
    VALUES
      (gen_random_uuid(), tpl.care_home_id, new_section_id, '150ml', '150ml', 1, false, false, true),
      (gen_random_uuid(), tpl.care_home_id, new_section_id, '200ml', '200ml', 2, false, false, true),
      (gen_random_uuid(), tpl.care_home_id, new_section_id, '280ml', '280ml', 3, false, false, true),
      (gen_random_uuid(), tpl.care_home_id, new_section_id, '330ml', '330ml', 4, false, false, true),
      (gen_random_uuid(), tpl.care_home_id, new_section_id, '500ml', '500ml', 5, false, false, true),
      (gen_random_uuid(), tpl.care_home_id, new_section_id, '1000ml', '1000ml', 6, false, false, true);
  END LOOP;
END $$;
""")


def downgrade() -> None:
    op.execute(f"""
DO $$
DECLARE
  tpl RECORD;
BEGIN
  FOR tpl IN
    SELECT t.id, t.care_home_id
    FROM care_templates t
    JOIN care_categories c ON c.id = t.category_id
    WHERE c.name = 'Nutrition & Hydration'
      AND t.name IN ({",".join(f"'{n}'" for n in MEAL_PATTERN_TEMPLATES)})
  LOOP
    DELETE FROM care_template_options WHERE section_id IN (
      SELECT id FROM care_template_sections WHERE template_id = tpl.id AND name = 'Meal Size Offered'
    );
    DELETE FROM care_template_sections WHERE template_id = tpl.id AND name = 'Meal Size Offered';
    UPDATE care_template_sections SET sort_order = 2 WHERE template_id = tpl.id AND name = 'Amount Eaten';

    INSERT INTO care_template_measurements (id, care_home_id, template_id, name, data_type, unit, is_required, sort_order)
    VALUES (gen_random_uuid(), tpl.care_home_id, tpl.id, 'Percentage Eaten', 'numeric', '%', false, 0);
  END LOOP;
END $$;
""")

    op.execute(f"""
DO $$
DECLARE
  tpl RECORD;
BEGIN
  FOR tpl IN
    SELECT t.id
    FROM care_templates t
    JOIN care_categories c ON c.id = t.category_id
    WHERE c.name = 'Nutrition & Hydration'
      AND t.name IN ({",".join(f"'{n}'" for n in DRINK_PATTERN_TEMPLATES)})
  LOOP
    DELETE FROM care_template_options WHERE section_id IN (
      SELECT id FROM care_template_sections WHERE template_id = tpl.id AND name = 'Quantity Offered'
    );
    DELETE FROM care_template_sections WHERE template_id = tpl.id AND name = 'Quantity Offered';
    UPDATE care_template_sections SET sort_order = 1 WHERE template_id = tpl.id AND name = 'Amount';
  END LOOP;
END $$;
""")
