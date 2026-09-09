"""RLS-scoped read projections; historical rows stay in their source tables.

Only static application constants enter SQL expressions. Never put client input
into table/column expressions or run these queries with a privileged DB role.
"""

# table, type, effective time, actor, aliases used by the generic API
DOMAIN_SOURCES = (
    ("fluid_intake_records", "fluid_intake", "recorded_at", "recorded_by", "jsonb_build_object('ml', t.volume_ml)"),
    (
        "food_intake_records",
        "meal",
        "recorded_at",
        "recorded_by",
        "jsonb_build_object('meal', t.meal_type, 'fraction_eaten', t.percentage_eaten / 100.0)",
    ),
    ("weight_records", "weight", "recorded_at", "recorded_by", "jsonb_build_object('kg', t.weight_kg)"),
    (
        "vital_signs_records",
        "vitals",
        "recorded_at",
        "recorded_by",
        "jsonb_build_object('systolic_bp', t.blood_pressure_systolic, "
        "'diastolic_bp', t.blood_pressure_diastolic, 'spo2_pct', t.oxygen_saturation_pct, "
        "'temperature_c', t.temperature_celsius)",
    ),
    ("mobility_observations", "mobility", "recorded_at", "recorded_by", "'{}'::jsonb"),
    ("continence_records", "continence", "recorded_at", "recorded_by", "'{}'::jsonb"),
    ("wellbeing_records", "wellbeing", "recorded_at", "recorded_by", "'{}'::jsonb"),
    ("behaviour_records", "behaviour", "occurred_at", "recorded_by", "'{}'::jsonb"),
    ("communication_logs", "communication", "recorded_at", "recorded_by", "'{}'::jsonb"),
    ("sleep_records", "sleep", "night_of", "recorded_by", "'{}'::jsonb"),
    ("pain_assessments", "pain", "assessed_at", "assessed_by", "'{}'::jsonb"),
    (
        "falls_incidents",
        "fall",
        "occurred_at",
        "reported_by",
        "jsonb_build_object('structured', jsonb_build_object('fall_mentioned', true))",
    ),
    ("incidents", "incident", "occurred_at", "reported_by", "'{}'::jsonb"),
    ("wound_records", "wound", "first_observed", None, "'{}'::jsonb"),
)

_METADATA = """ARRAY[
    'id', 'care_home_id', 'floor_id', 'resident_id', 'recorded_at', 'occurred_at',
    'assessed_at', 'created_at', 'updated_at', 'deleted_at', 'recorded_by',
    'assessed_by', 'reported_by'
]"""


def _domain_select(table: str, kind: str, time_column: str, actor: str | None, aliases: str) -> str:
    date_only = time_column in {"night_of", "first_observed"}
    effective_time = f"t.{time_column}::timestamp AT TIME ZONE h.timezone" if date_only else f"t.{time_column}"
    source_date = f"t.{time_column}::text" if date_only else "NULL::text"
    actor_column = f"t.{actor}" if actor else "NULL::uuid"
    return f"""
        SELECT t.id, t.resident_id, '{kind}'::text AS type,
            jsonb_strip_nulls((to_jsonb(t) - {_METADATA}) || {aliases}) AS value,
            {effective_time} AS recorded_at, {actor_column} AS recorded_by,
            false AS is_implausible, '{table}'::text AS source_type,
            '{"date" if date_only else "timestamp"}'::text AS time_precision,
            {source_date} AS source_date
        FROM {table} t
        JOIN residents r ON r.id = t.resident_id AND r.care_home_id = t.care_home_id
        JOIN care_homes h ON h.id = t.care_home_id
        WHERE t.deleted_at IS NULL AND r.deleted_at IS NULL
    """


CLINICAL_FEED_SQL = "\nUNION ALL\n".join(
    [
        """
        SELECT t.id, t.resident_id, t.type::text AS type, t.value,
            t.recorded_at, t.recorded_by, t.is_implausible,
            'observations'::text AS source_type, 'timestamp'::text AS time_precision,
            NULL::text AS source_date
        FROM observations t
        JOIN residents r ON r.id = t.resident_id AND r.care_home_id = t.care_home_id
        WHERE t.deleted_at IS NULL AND r.deleted_at IS NULL
    """,
        *[_domain_select(*source) for source in DOMAIN_SOURCES],
    ]
)

SOURCE_TYPES = frozenset({"observations", *(source[0] for source in DOMAIN_SOURCES)})
