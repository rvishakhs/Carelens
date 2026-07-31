import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base, TenantMixin


class FloorType(str, enum.Enum):
    DEMENTIA = "dementia"
    RESIDENTIAL = "residential"
    NURSING = "nursing"
    OTHER = "other"


class Floor(Base, TenantMixin):
    """A finer-grained tenancy dimension underneath care_home_id -- see
    migrations/versions/0013's docstring for the authorisation-vs-session-selection
    design this and UserFloorLink implement."""

    __tablename__ = "floors"

    name: Mapped[str] = mapped_column(String(255))
    floor_type: Mapped[FloorType] = mapped_column(
        Enum(FloorType, name="floor_type", values_callable=lambda e: [m.value for m in e]),
        default=FloorType.OTHER,
    )
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)


class UserFloorLink(Base, TenantMixin):
    """Which floors a user is EVER allowed to see (rarely changes, set by a
    manager/headoffice) -- distinct from the `app.floor_ids` session GUC, which is
    which of these the user has selected/requested for the current session. See
    app/modules/floors/repository.py for how the two get reconciled."""

    __tablename__ = "user_floor_links"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    floor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("floors.id"), index=True)
    granted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = ["Floor", "FloorType", "UserFloorLink"]
