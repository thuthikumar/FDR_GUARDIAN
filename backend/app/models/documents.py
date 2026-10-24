"""Private document metadata and separately stored extracted values."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.db.constraints import enum_check
from app.models.enums import DocumentType, ProcessingStatus, ReviewStatus


class Document(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        enum_check("document_type", DocumentType),
        enum_check("processing_status", ProcessingStatus),
        enum_check("review_status", ReviewStatus),
        CheckConstraint("file_size >= 0", name="file_size_nonnegative"),
        Index("ix_documents_fdr_record_id", "fdr_record_id"),
    )

    fdr_record_id: Mapped[UUID] = mapped_column(
        ForeignKey("fdr_records.id", ondelete="RESTRICT"), nullable=False
    )
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    private_storage_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_size: Mapped[int] = mapped_column(nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64))
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processing_status: Mapped[str] = mapped_column(String(24), nullable=False)
    review_status: Mapped[str] = mapped_column(String(24), nullable=False)


class ExtractedField(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "extracted_fields"
    __table_args__ = (
        UniqueConstraint("document_id", "field_name", name="document_field"),
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name="confidence_range",
        ),
        Index("ix_extracted_fields_document_id", "document_id"),
    )

    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False)
    field_name: Mapped[str] = mapped_column(String(80), nullable=False)
    extracted_value: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    extraction_method: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewer_confirmed_value: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
