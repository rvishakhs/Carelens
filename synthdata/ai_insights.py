"""Populates migration 0016's AI-generated knowledge layer with a plausible sample per
resident, derived from the trajectory that actually shaped their data -- not invented
independently of it, so the narrative text is at least consistent with what a real
read of the generated records would show. Without this, the whole AI-insights layer
(summaries/reports/alerts/predictions) exists as empty tables in every synthetic
dataset, which defeats the point of a demo/dev fixture for the AI layer.

Timestamps are derived from window_end (deterministic, like everything else in
synthdata -- see generator.py's docstring), not datetime.now().
"""

import random
import uuid
from datetime import UTC, date, datetime, time, timedelta

from synthdata.daily_records import ResidentContext
from synthdata.ids import seeded_uuid

_MODEL_NAME = "claude-sonnet-4-6"

# (report_type, version_label, prompt_text) -- shared, care-home-wide reference data
# (ai_prompt_versions has no care_home_id at all, per migration 0016's own note).
_PROMPT_VERSIONS = [
    ("weekly_summary", "v1", "Summarise this resident's care over the past 7 days across nutrition, mobility, mood and any notable events."),
    ("deterioration_risk", "v1", "Given this resident's recent trend data, identify whether there are early signs of deterioration, and explain the evidence behind the assessment."),
    ("mobility_report", "v1", "Summarise mobility trend, falls history, and reassessment outcomes for this resident over the reporting period."),
]


def build_prompt_versions(rng: random.Random) -> list[dict]:
    return [
        {
            "id": seeded_uuid(rng),
            "report_type": report_type,
            "version_label": version_label,
            "prompt_text": prompt_text,
            "model_name": _MODEL_NAME,
            "is_active": True,
        }
        for report_type, version_label, prompt_text in _PROMPT_VERSIONS
    ]


def _at(day: date, t: time) -> datetime:
    return datetime.combine(day, t, tzinfo=UTC)


def build_resident_ai_outputs(
    rng: random.Random,
    ctx: ResidentContext,
    prompt_version_ids: dict[str, uuid.UUID],
    window_start: date,
    window_end: date,
) -> dict[str, list[dict]]:
    """One resident's worth of AI output rows, shaped by ctx.trajectory_name. Every
    output traces back to a generation log, which traces back to a prompt version --
    the same provenance chain migration 0016 was designed around."""
    generated_at = _at(window_end + timedelta(days=1), time(6, 0))
    period_start = _at(max(window_start, window_end - timedelta(days=6)), time(0, 0))
    period_end = _at(window_end, time(23, 59))

    rows: dict[str, list[dict]] = {
        "ai_generation_logs": [], "resident_ai_summaries": [], "resident_ai_reports": [],
        "resident_ai_alerts": [], "resident_predictions": [],
    }

    summary_log_id = seeded_uuid(rng)
    rows["ai_generation_logs"].append(
        _generation_log(rng, summary_log_id, ctx, "weekly_summary", prompt_version_ids["weekly_summary"], period_start, period_end, generated_at)
    )
    rows["resident_ai_summaries"].append(
        _summary(rng, ctx, summary_log_id, prompt_version_ids["weekly_summary"], period_start, period_end, generated_at)
    )

    if ctx.trajectory_name == "gradual_decline":
        risk_log_id = seeded_uuid(rng)
        rows["ai_generation_logs"].append(
            _generation_log(rng, risk_log_id, ctx, "deterioration_risk", prompt_version_ids["deterioration_risk"], period_start, period_end, generated_at)
        )
        rows["resident_ai_alerts"].append(
            _alert(
                rng, ctx, risk_log_id, prompt_version_ids["deterioration_risk"], generated_at,
                alert_type="deterioration_risk", severity="warning", status="open",
                alert_text=(
                    f"{ctx.persona.preferred_name or ctx.persona.first_name}'s appetite, fluid intake and mood scores have "
                    "trended downward over the review window, with reduced mobility assessment scores and increased sleep "
                    "disruption noted in the same period. Recommend a clinical review to rule out an underlying cause."
                ),
            )
        )
        rows["resident_predictions"].append(
            _prediction(
                rng, ctx, risk_log_id, prompt_version_ids["deterioration_risk"], generated_at,
                prediction_type="deterioration_risk", horizon_days=14, confidence=round(rng.uniform(0.72, 0.91), 3),
                prediction_text=(
                    "Pattern of declining appetite, fluid intake and mobility over the past few weeks is consistent with "
                    "early functional deterioration. This is a pattern to review, not a diagnosis."
                ),
                recommended_action="Prompts for clinical review of nutrition, hydration and mobility trend.",
            )
        )
    elif ctx.trajectory_name == "post_fall_recovery":
        mobility_log_id = seeded_uuid(rng)
        rows["ai_generation_logs"].append(
            _generation_log(rng, mobility_log_id, ctx, "mobility_report", prompt_version_ids["mobility_report"], period_start, period_end, generated_at)
        )
        rows["resident_ai_alerts"].append(
            _alert(
                rng, ctx, mobility_log_id, prompt_version_ids["mobility_report"], generated_at,
                alert_type="fall_risk_increase", severity="warning", status="resolved",
                alert_text=f"{ctx.persona.preferred_name or ctx.persona.first_name} had a fall during the review period. Falls risk score was elevated on reassessment.",
                resolution_note="Post-fall care plan and physiotherapy review completed; mobility has since stabilised.",
            )
        )
        rows["resident_ai_reports"].append(
            _report(
                rng, ctx, mobility_log_id, prompt_version_ids["mobility_report"], period_start, period_end, generated_at,
                report_domain="mobility",
                report_text=(
                    "Following a fall earlier in the period, mobility and appetite dipped before showing a steady recovery "
                    "trend, consistent with the post-fall care plan and increased physiotherapy input."
                ),
                structured_findings={"falls_in_period": 1, "trend": "recovering"},
            )
        )
    elif ctx.trajectory_name == "uti_episode":
        infection_log_id = seeded_uuid(rng)
        rows["ai_generation_logs"].append(
            _generation_log(rng, infection_log_id, ctx, "deterioration_risk", prompt_version_ids["deterioration_risk"], period_start, period_end, generated_at)
        )
        rows["resident_ai_alerts"].append(
            _alert(
                rng, ctx, infection_log_id, prompt_version_ids["deterioration_risk"], generated_at,
                alert_type="possible_infection", severity="urgent", status="resolved",
                alert_text=(
                    f"{ctx.persona.preferred_name or ctx.persona.first_name} showed a cluster of new confusion, reduced fluid "
                    "intake and increased continence events over a short period, a pattern often associated with a urinary "
                    "tract infection."
                ),
                resolution_note="GP review confirmed a UTI; antibiotic course completed and resident returned to baseline.",
            )
        )

    return rows


def _generation_log(rng, log_id, ctx: ResidentContext, report_type, prompt_version_id, period_start, period_end, generated_at) -> dict:
    return {
        "id": log_id,
        "care_home_id": ctx.care_home_id,
        "resident_id": ctx.resident_id,
        "report_type": report_type,
        "prompt_version_id": prompt_version_id,
        "input_event_ids": [],
        "input_event_count": rng.randint(15, 80),
        "period_start": period_start,
        "period_end": period_end,
        "status": "completed",
        "error_message": None,
        "latency_ms": rng.randint(800, 4000),
        "started_at": generated_at - timedelta(seconds=5),
        "completed_at": generated_at,
    }


def _summary(rng, ctx: ResidentContext, log_id, prompt_version_id, period_start, period_end, generated_at) -> dict:
    name = ctx.persona.preferred_name or ctx.persona.first_name
    text_by_trajectory = {
        "stable": f"{name} has had a settled week. Nutrition, mobility and mood remain consistent with their usual baseline; no new concerns identified.",
        "gradual_decline": f"{name}'s intake, mood and mobility scores have trended downward this week compared to prior weeks. See the linked deterioration-risk alert for details.",
        "post_fall_recovery": f"{name} is recovering well following a recent fall, with appetite and mobility gradually returning toward baseline.",
        "uti_episode": f"{name} experienced a short period of increased confusion and reduced intake this week, since resolved -- see the linked alert.",
    }
    return {
        "id": seeded_uuid(rng),
        "care_home_id": ctx.care_home_id,
        "resident_id": ctx.resident_id,
        "summary_type": "weekly",
        "period_start": period_start,
        "period_end": period_end,
        "generation_log_id": log_id,
        "prompt_version_id": prompt_version_id,
        "input_event_count": rng.randint(15, 80),
        "summary_text": text_by_trajectory[ctx.trajectory_name],
        "supersedes_id": None,
        "is_current": True,
        "feedback_rating": None,
        "feedback_comment": None,
        "feedback_by": None,
        "feedback_at": None,
        "generated_at": generated_at,
    }


def _alert(rng, ctx: ResidentContext, log_id, prompt_version_id, generated_at, *, alert_type, severity, status, alert_text, resolution_note=None) -> dict:
    reviewer = rng.choice(ctx.staff_user_ids) if status != "open" else None
    return {
        "id": seeded_uuid(rng),
        "care_home_id": ctx.care_home_id,
        "resident_id": ctx.resident_id,
        "alert_type": alert_type,
        "severity": severity,
        "generation_log_id": log_id,
        "prompt_version_id": prompt_version_id,
        "triggering_event_ids": [],
        "alert_text": alert_text,
        "status": status,
        "acknowledged_by": reviewer,
        "acknowledged_at": generated_at + timedelta(hours=4) if reviewer else None,
        "resolution_note": resolution_note,
        "generated_at": generated_at,
    }


def _prediction(rng, ctx: ResidentContext, log_id, prompt_version_id, generated_at, *, prediction_type, horizon_days, confidence, prediction_text, recommended_action) -> dict:
    return {
        "id": seeded_uuid(rng),
        "care_home_id": ctx.care_home_id,
        "resident_id": ctx.resident_id,
        "prediction_type": prediction_type,
        "horizon_days": horizon_days,
        "confidence": confidence,
        "generation_log_id": log_id,
        "prompt_version_id": prompt_version_id,
        "input_event_ids": [],
        "prediction_text": prediction_text,
        "recommended_action": recommended_action,
        "status": "active",
        "generated_at": generated_at,
    }


def _report(rng, ctx: ResidentContext, log_id, prompt_version_id, period_start, period_end, generated_at, *, report_domain, report_text, structured_findings) -> dict:
    return {
        "id": seeded_uuid(rng),
        "care_home_id": ctx.care_home_id,
        "resident_id": ctx.resident_id,
        "report_domain": report_domain,
        "period_start": period_start,
        "period_end": period_end,
        "generation_log_id": log_id,
        "prompt_version_id": prompt_version_id,
        "input_event_count": rng.randint(10, 50),
        "report_text": report_text,
        "structured_findings": structured_findings,
        "supersedes_id": None,
        "is_current": True,
        "feedback_rating": None,
        "feedback_comment": None,
        "feedback_by": None,
        "feedback_at": None,
        "generated_at": generated_at,
    }