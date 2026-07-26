import enum
from datetime import date

from sqlalchemy import Boolean, Date, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base, TenantMixin


class ResidentStatus(str, enum.Enum):
    ACTIVE = "active"
    DISCHARGED = "discharged"
    DECEASED = "deceased"


class Resident(Base, TenantMixin):
    __tablename__ = "residents"

    first_name: Mapped[str] = mapped_column(String(255))
    last_name: Mapped[str] = mapped_column(String(255))
    date_of_birth: Mapped[date] = mapped_column(Date)
    room: Mapped[str] = mapped_column(String(50))
    status: Mapped[ResidentStatus] = mapped_column(
        Enum(ResidentStatus, name="resident_status"), default=ResidentStatus.ACTIVE
    )

    # Consent flags -- Phase 1 keeps these minimal; family/consent machinery is Phase 5.
    data_processing_consent: Mapped[bool] = mapped_column(Boolean, default=True)
    photo_consent: Mapped[bool] = mapped_column(Boolean, default=False)


__all__ = ["Resident", "ResidentStatus"]