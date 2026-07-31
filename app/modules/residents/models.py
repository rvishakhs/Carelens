import enum
import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base, TenantMixin


class ResidentStatus(str, enum.Enum):
    ACTIVE = "active"
    DISCHARGED = "discharged"
    HOSPITALIZED = "hospitalized"
    ARCHIVED = "archived"


class Resident(Base, TenantMixin):
    __tablename__ = "residents"

    first_name: Mapped[str] = mapped_column(Text)
    last_name: Mapped[str] = mapped_column(Text)
    preferred_name: Mapped[str | None] = mapped_column(Text)

    date_of_birth: Mapped[date] = mapped_column(Date)
    nhs_number: Mapped[str | None] = mapped_column(Text)
    gender: Mapped[str | None] = mapped_column(Text)

    room_number: Mapped[str | None] = mapped_column(Text)

    # Nullable: migration 0013's fail-closed default -- a resident invisible under
    # floor-scoped RLS until a manager assigns them to a floor.
    floor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("floors.id"), nullable=True)

    admission_date: Mapped[date] = mapped_column(Date)
    discharge_date: Mapped[date | None] = mapped_column(Date)

    # migrations/versions/0003: `status` is plain TEXT (app-level convention, not a
    # native Postgres enum) -- native_enum=False keeps SQLAlchemy from generating an
    # `::resident_status` cast against a PG type that doesn't exist.
    status: Mapped[ResidentStatus] = mapped_column(
        Enum(
            ResidentStatus,
            name="resident_status",
            native_enum=False,
            values_callable=lambda enum: [e.value for e in enum],
        ),
        default=ResidentStatus.ACTIVE,
    )

    gp_practice_name: Mapped[str | None] = mapped_column(Text)
    gp_phone: Mapped[str | None] = mapped_column(Text)

    photo_url: Mapped[str | None] = mapped_column(Text)


__all__ = ["Resident", "ResidentStatus"]
