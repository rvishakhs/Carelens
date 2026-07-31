"""Public interface other modules depend on -- identity imports FloorReader from here
(to resolve a user's authorised floors right after login) and get_floor_reader from
dependencies.py, never floors.repository or floors.models directly."""

import abc
import uuid


class FloorReader(abc.ABC):
    @abc.abstractmethod
    async def get_authorized_floor_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        """Every floor this user has an active (non-revoked) link to -- their full
        authorisation, not a per-session subset. Callers wanting "everything they can
        see" (the common case, absent a floor-picker UI) pass this straight into
        rls_session(); a future floor-picker would intersect this list with what the
        user requested for that session."""
        ...
