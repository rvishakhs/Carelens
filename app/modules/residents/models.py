import enum
from datetime import date

from sqlalchemy import Date, Enum, Text
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

    admission_date: Mapped[date] = mapped_column(Date)
    discharge_date: Mapped[date | None] = mapped_column(Date)

    status: Mapped[ResidentStatus] = mapped_column(
        Enum(ResidentStatus, name="resident_status", values_callable=lambda enum: [e.value for e in enum]),
        default=ResidentStatus.ACTIVE,
    )

    gp_practice_name: Mapped[str | None] = mapped_column(Text)
    gp_phone: Mapped[str | None] = mapped_column(Text)

    photo_url: Mapped[str | None] = mapped_column(Text)


__all__ = ["Resident", "ResidentStatus"]
