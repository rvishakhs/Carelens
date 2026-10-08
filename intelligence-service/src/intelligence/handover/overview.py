"""Concise review overview over validated claims, retaining unfamiliar detail.

This is not a deterioration detector or an assessment against individual targets.
Only recognised care-event facts are condensed. Other clinical claims remain visible.
"""

import json
import re
from decimal import Decimal, InvalidOperation

from intelligence.handover.contracts import HandoverSection
from intelligence.handover.prose import number

PHRASES = {
    "the meal included a sandwich": "food_sandwich",
    "a medium meal portion was offered": "meal_size_medium",
    "the walking distance was recorded as medium": "distance_medium",
    "the trigger was recorded as unknown": "trigger_unknown",
    "the drink was tea": "drink_tea",
    "wandering was recorded in the garden": "wandering_in_garden",
    "most of the meal was eaten": "meal_most_eaten",
    "about half of the meal was eaten": "meal_about_half_eaten",
    "half of the drink was recorded as taken": "amount_half",
    "all of the drink was recorded as taken": "amount_all",
    "a walk was recorded": "is_walk",
    "wandering was recorded": "is_wandering",
    "a walking frame was used": "walking_frame_used",
    "assistance was recorded as supervision only": "supervision_only",
    "the recorded response was settled": "settled",
    "the resident remained on the premises": "remained_on_premises",
    "reassurance or distraction was recorded": "reassurance_or_distraction",
}
ALLOWED = {*PHRASES.values(), "status_completed", "duration_minutes", "offered_ml", "estimated_consumed_ml"}


def care_facts(claim) -> dict | None:
    if len(claim.sources) != 1 or claim.sources[0].source_type != "care_events":
        return None
    text = claim.text
    # Legacy originals are normally formatted before this function; support both.
    if text.startswith("Clinical event time: ") and ". Recorded content: " in text:
        try:
            fields = json.loads(text.split(". Recorded content: ", 1)[1])
        except ValueError:
            return None
        if not isinstance(fields, dict) or not fields.keys() <= ALLOWED:
            return None
        return fields if fields.get("status_completed") is True else None
    match = re.fullmatch(r"At \d{2}:\d{2} on \d{2} [A-Za-z]{3}: (.+)\.", text)
    if not match:
        return None
    fields = {}
    for clause in match[1].split("; "):
        if clause in PHRASES:
            fields[PHRASES[clause]] = True
        elif re.fullmatch(r"[0-9.]+ ml of fluid was offered", clause):
            fields["offered_ml"] = clause.split()[0]
        elif re.fullmatch(
            r"intake was estimated at [0-9.]+ ml from (half taken|all taken|recorded choices), not measured",
            clause,
        ):
            fields["estimated_consumed_ml"] = clause.split()[4]
            if "half taken" in clause:
                fields["amount_half"] = True
            elif "all taken" in clause:
                fields["amount_all"] = True
        elif re.fullmatch(r"the care event duration was recorded as [0-9.]+ minutes", clause):
            pass
        else:
            # Includes refusals, arbitrary notes, unknown assistance and contradictions.
            return None
    return fields or None


def overview_text(sections: tuple[HandoverSection, ...]) -> str | None:
    paragraphs = []
    condensed_any = False
    # Recorded incidents and behaviour precede routine intake/mobility.
    priority = {"falls_incidents": 0, "pain": 1, "nutrition_hydration": 2, "mobility": 3, "mood_behaviour": 4}
    for section in sorted(sections, key=lambda s: priority.get(s.category, 3)):
        recognised = [(claim, care_facts(claim)) for claim in section.claims]
        facts = [value for _, value in recognised if value is not None]
        summary = []
        if facts and section.category == "nutrition_hydration":
            most = any(f.get("meal_most_eaten") is True for f in facts)
            half = any(f.get("meal_about_half_eaten") is True for f in facts)
            if most and half:
                summary.append("Meal intake varied between about half and most of the portions recorded.")
            elif most:
                meals = [f for f in facts if f.get("meal_most_eaten")]
                food = " (including a sandwich)" if all(f.get("food_sandwich") for f in meals) else ""
                summary.append(f"The resident ate most of the recorded meal portions{food}.")
            elif half:
                summary.append("Meal records describe about half of the food being eaten.")
            drinks = [f for f in facts if "offered_ml" in f or f.get("amount_half") or f.get("amount_all")]
            if drinks:
                amounts = {
                    "half" if f.get("amount_half") else "all" if f.get("amount_all") else "unknown"
                    for f in drinks
                }
                try:
                    estimates = [Decimal(str(f["estimated_consumed_ml"])) for f in drinks]
                    identities = [c.sources[0].source_id for c, f in recognised if f in drinks]
                    can_total = len(identities) == len(set(identities)) and all(
                        value.is_finite() and value >= 0 for value in estimates
                    )
                except (KeyError, InvalidOperation):
                    estimates, can_total = [], False
                if can_total:
                    total = number(sum(estimates, Decimal(0)))
                    tea = (
                        ", including tea taken in full"
                        if any(f.get("drink_tea") and f.get("amount_all") for f in drinks)
                        else ""
                    )
                    summary.append(
                        f"Estimated fluid intake was approximately {total} ml across {len(drinks)} "
                        f"recorded {'drink' if len(drinks) == 1 else 'drinks'}{tea}."
                    )
                elif amounts == {"half", "all"}:
                    summary.append("Recorded drinks were partly or fully taken.")
                elif amounts == {"all"}:
                    summary.append("Recorded drinks were taken in full.")
                elif amounts == {"half"}:
                    summary.append("Recorded drinks were half taken.")
                else:
                    summary.append("Drinks were offered; consumption was not consistently recorded.")
        elif facts and section.category == "mobility":
            walks = [f for f in facts if f.get("is_walk") is True]
            if walks:
                # Generalise only when every recognised walk supports the same assistance.
                frame = all(f.get("walking_frame_used") is True for f in walks)
                supervised = all(f.get("supervision_only") is True for f in walks)
                support = (
                    " with a walking frame and supervision"
                    if frame and supervised
                    else (" with a walking frame" if frame else " with supervision" if supervised else "")
                )
                distance = (
                    "a medium-distance walk"
                    if len(walks) == 1 and walks[0].get("distance_medium")
                    else "walking"
                )
                summary.append(
                    f"Mobility was supported during {distance}{support}."
                    if support
                    else "Walking was documented."
                )
                if not (frame and supervised):
                    summary.append("Support details vary or are incomplete; see the care records.")
        elif facts and section.category == "mood_behaviour":
            wandering = [f for f in facts if f.get("is_wandering") is True]
            if wandering:
                location = " in the garden" if all(f.get("wandering_in_garden") for f in wandering) else ""
                trigger = (
                    ", with the trigger recorded as unknown"
                    if all(f.get("trigger_unknown") for f in wandering)
                    else ""
                )
                summary.append(f"Wandering was noted{location}{trigger}.")
                response = []
                if all(f.get("reassurance_or_distraction") is True for f in wandering):
                    response.append("Staff documented reassurance or distraction")
                if all(f.get("settled") is True for f in wandering):
                    response.append("a settled response")
                if all(f.get("remained_on_premises") is True for f in wandering):
                    response.append("the resident remaining on the premises")
                if response:
                    if not response[0].startswith("Staff"):
                        response[0] = "The records describe " + response[0]
                    summary.append(
                        ", ".join(response[:-1]) + (" and " if len(response) > 1 else "") + response[-1] + "."
                    )
            elif all(f.get("settled") is True for f in facts):
                summary.append("The recorded responses were settled.")
        if summary:
            condensed_any = True
            paragraphs.append(" ".join(summary))
            # Do not hide unrecognised clinical details or risk-related statements.
            for claim, value in recognised:
                if value is not None:
                    # Uncovered facts in another type of event must remain visible.
                    covered = (
                        section.category == "nutrition_hydration"
                        and any(
                            k in value
                            for k in (
                                "meal_most_eaten",
                                "meal_about_half_eaten",
                                "offered_ml",
                                "amount_half",
                                "amount_all",
                            )
                        )
                        or section.category == "mobility"
                        and value.get("is_walk")
                        or section.category == "mood_behaviour"
                        and (value.get("is_wandering") or value.get("settled"))
                    )
                    if covered:
                        continue
                if claim.text.startswith(
                    (
                        "Recorded fluid offered:",
                        "Recorded fluid offered total:",
                        "Recorded fluid intake (excluding estimates)",
                    )
                ):
                    continue  # Totals remain in the evidence panel, not the overview.
                paragraphs.append(claim.text)
        else:
            paragraphs.extend(claim.text for claim in section.claims)
    return " ".join(paragraphs) if condensed_any else None
