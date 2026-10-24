"""Institution persistence model."""

from uuid import UUID

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.constraints import enum_check
from app.models.enums import InstitutionStatus


class Institution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "institutions"
    __table_args__ = (enum_check("status", InstitutionStatus),)

    institution_code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    institution_name: Mapped[str] = mapped_column(String(200), nullable=False)
    institution_type: Mapped[str | None] = mapped_column(String(80))
    state: Mapped[str | None] = mapped_column(String(80))
    contact_email: Mapped[str | None] = mapped_column(String(254))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=InstitutionStatus.ACTIVE.value)
    is_synthetic: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
