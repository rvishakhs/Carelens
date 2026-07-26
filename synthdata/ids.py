"""Deterministic UUIDs -- every row's `id` is derived from the run's seeded Random
instance instead of the process-random `uuid.uuid4()`, so the same --seed genuinely
reproduces the same dataset byte-for-byte (not just the same shape of values), which
is what makes it usable as a fixture in tests and demos."""

import random
import uuid


def seeded_uuid(rng: random.Random) -> uuid.UUID:
    return uuid.UUID(int=rng.getrandbits(128))
