"""Fixed Deposit Receipt record model."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.constraints import enum_check
from app.models.enums import FDRRecordStatus, VerificationStatus


class FDRRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fdr_records"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("maturity_date > issue_date", name="maturity_after_issue"),
        enum_check("record_status", FDRRecordStatus),
        enum_check("verification_status", VerificationStatus),
        Index("ix_fdr_records_source_external_not_null", "source_system", "external_record_id", unique=True,
              postgresql_where=text("external_record_id IS NOT NULL")),
        Index("ix_fdr_records_fdr_number", "fdr_number"),
        Index("ix_fdr_records_institution_fdr_number", "institution_id", "fdr_number"),
        Index("ix_fdr_records_maturity_date", "maturity_date"),
        Index("ix_fdr_records_record_status", "record_status"),
        Index("ix_fdr_records_verification_status", "verification_status"),
        Index("ix_fdr_records_institution_id", "institution_id"),
    )

    institution_id: Mapped[UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="RESTRICT"), nullable=False
    )
    internal_fdr_id: Mapped[str] = mapped_column(String(48), nullable=False, unique=True)
    external_record_id: Mapped[str | None] = mapped_column(String(120))
    bank_name: Mapped[str] = mapped_column(String(160), nullable=False)
    branch_name: Mapped[str | None] = mapped_column(String(160))
    fdr_number: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR", server_default="INR")
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    maturity_date: Mapped[date] = mapped_column(Date, nullable=False)
    record_status: Mapped[str] = mapped_column(String(24), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_system: Mapped[str] = mapped_column(String(64), nullable=False, default="SYNTHETIC_DEMO")
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_synthetic: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
