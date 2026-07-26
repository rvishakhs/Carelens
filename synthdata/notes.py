"""Generates carer-shorthand free-text notes from templates + variation, including
occasional typos, so summarisation and the pseudonymiser fixture suite have realistic
input instead of clean prose."""

import random

_TEMPLATES = {
    "stable": ["Settled today, ate {appetite_desc}, no concerns.", "Comfortable shift, {fluid_desc} fluids taken."],
    "low": ["Seemed tearful this morning, reassured x2.", "Low mood noted, declined activities."],
    "agitated": ["Confused and restless overnight, redirected to bed x3.", "Distressed at times, 1:1 support given."],
}

_TYPO_SUBSTITUTIONS = {"the": "teh", "and": "adn", "with": "wiht"}


def _appetite_desc(multiplier: float) -> str:
    if multiplier > 0.9:
        return "well"
    if multiplier > 0.6:
        return "a little"
    return "poorly"


def _fluid_desc(multiplier: float) -> str:
    return "good" if multiplier > 0.8 else "reduced"


def generate_note(mood: str | None, appetite_multiplier: float, fluid_multiplier: float, rng: random.Random) -> str:
    mood_key = mood if mood in _TEMPLATES else "stable"
    template = rng.choice(_TEMPLATES[mood_key])
    text = template.format(appetite_desc=_appetite_desc(appetite_multiplier), fluid_desc=_fluid_desc(fluid_multiplier))

    if rng.random() < 0.15:
        for word, typo in _TYPO_SUBSTITUTIONS.items():
            if word in text:
                text = text.replace(word, typo, 1)
                break

    return text
