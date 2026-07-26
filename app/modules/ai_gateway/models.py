import uuid

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base, TenantMixin


class PseudonymMapping(Base, TenantMixin):
    """Stable per-resident token <-> resident_id mapping. Lives only here -- never in
    an LLM prompt, a log line, or an ai_outputs row. Re-identifying a gateway response
    is the only reason this table exists."""

    __tablename__ = "pseudonym_mappings"
    __table_args__ = (UniqueConstraint("care_home_id", "resident_id", name="uq_pseudonym_mapping_resident"),)

    resident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    token: Mapped[str] = mapped_column(String(32), unique=True, index=True)


__all__ = ["PseudonymMapping"]
