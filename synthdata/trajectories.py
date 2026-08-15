"""Scriptable trajectories bias a persona's day-to-day values across the simulation
window, across every clinical domain the real schema tracks. `gradual_decline` is the
Phase 2 change-detection target -- keep each trajectory's signature clear and
inspectable rather than folding it into generic noise.
"""

import abc
import dataclasses
import random
from collections.abc import Callable


@dataclasses.dataclass(frozen=True)
class DailyBias:
    appetite_multiplier: float = 1.0
    fluid_multiplier: float = 1.0
    mood: str | None = None               # matches mood_state enum labels when set
    fall_today: bool = False
    confusion_spike: bool = False
    pain_flag: bool = False               # elevated chance of a pain assessment + PRN analgesia today
    skin_risk_elevated: bool = False      # elevated chance of a wound / skin concern today
    sleep_disruption: bool = False        # more night wakings, poorer sleep quality
    continence_event_multiplier: float = 1.0
    # 0..1, only meaningful for gradual_decline (its `progress`) -- periodic
    # mobility/skin reassessments (daily_records.py) read this to drift scores
    # upward over the window instead of reassessing at a flat baseline every time.
    decline_severity: float = 0.0


class Trajectory(abc.ABC):
    @abc.abstractmethod
    def bias_for_day(self, day_index: int, total_days: int, rng: random.Random) -> DailyBias: ...


class StableTrajectory(Trajectory):
    def bias_for_day(self, day_index: int, total_days: int, rng: random.Random) -> DailyBias:
        return DailyBias(appetite_multiplier=rng.uniform(0.9, 1.05), fluid_multiplier=rng.uniform(0.9, 1.05))


class GradualDeclineTrajectory(Trajectory):
    """A slow, roughly monotonic drift downward across the window -- what Phase 2's
    detection rules are meant to catch before it becomes a crisis."""

    def bias_for_day(self, day_index: int, total_days: int, rng: random.Random) -> DailyBias:
        progress = day_index / max(total_days - 1, 1)
        return DailyBias(
            appetite_multiplier=max(0.4, 1.0 - 0.5 * progress) * rng.uniform(0.95, 1.05),
            fluid_multiplier=max(0.5, 1.0 - 0.4 * progress) * rng.uniform(0.95, 1.05),
            mood="low" if progress > 0.6 else None,
            skin_risk_elevated=progress > 0.7 and rng.random() < 0.3,
            sleep_disruption=progress > 0.5 and rng.random() < 0.3,
            decline_severity=progress,
        )


class PostFallRecoveryTrajectory(Trajectory):
    def __init__(self, fall_day: int):
        self._fall_day = fall_day

    def bias_for_day(self, day_index: int, total_days: int, rng: random.Random) -> DailyBias:
        if day_index == self._fall_day:
            return DailyBias(
                appetite_multiplier=0.7, fluid_multiplier=0.8, fall_today=True, mood="agitated", pain_flag=True
            )
        days_since = day_index - self._fall_day
        if 0 < days_since <= 14:
            recovery = min(days_since / 14, 1.0)
            return DailyBias(
                appetite_multiplier=0.7 + 0.3 * recovery,
                fluid_multiplier=0.8 + 0.2 * recovery,
                pain_flag=days_since <= 5 and rng.random() < 0.6,
                sleep_disruption=days_since <= 7,
            )
        return DailyBias(appetite_multiplier=rng.uniform(0.9, 1.05), fluid_multiplier=rng.uniform(0.9, 1.05))


class UtiEpisodeTrajectory(Trajectory):
    def __init__(self, onset_day: int, duration_days: int = 5):
        self._onset_day = onset_day
        self._duration_days = duration_days

    def bias_for_day(self, day_index: int, total_days: int, rng: random.Random) -> DailyBias:
        days_in = day_index - self._onset_day
        if 0 <= days_in < self._duration_days:
            return DailyBias(
                appetite_multiplier=0.7,
                fluid_multiplier=0.6,
                mood="agitated",
                confusion_spike=True,
                continence_event_multiplier=1.6,
                sleep_disruption=True,
            )
        return DailyBias(appetite_multiplier=rng.uniform(0.9, 1.05), fluid_multiplier=rng.uniform(0.9, 1.05))


TRAJECTORIES: dict[str, Callable[[random.Random, int], Trajectory]] = {
    "stable": lambda rng, total_days: StableTrajectory(),
    "gradual_decline": lambda rng, total_days: GradualDeclineTrajectory(),
    "post_fall_recovery": lambda rng, total_days: PostFallRecoveryTrajectory(
        fall_day=rng.randint(total_days // 3, max(total_days // 2, total_days // 3 + 1))
    ),
    "uti_episode": lambda rng, total_days: UtiEpisodeTrajectory(
        onset_day=rng.randint(total_days // 3, max(2 * total_days // 3, total_days // 3 + 1))
    ),
}
