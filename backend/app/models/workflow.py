"""Verification cases, immutable approval actions, and explicit release events."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.db.constraints import enum_check
from app.models.enums import ApprovalActionType, ApprovalDecision, WorkflowStatus


class VerificationCase(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "verification_cases"
    __table_args__ = (
        enum_check("status", WorkflowStatus),
        Index("ix_verification_cases_status", "status"),
        Index("ix_verification_cases_fdr_record_id", "fdr_record_id"),
    )

    fdr_record_id: Mapped[UUID] = mapped_column(ForeignKey("fdr_records.id", ondelete="RESTRICT"), nullable=False)
    assigned_officer_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[str | None] = mapped_column(String(24))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApprovalAction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "approval_actions"
    __table_args__ = (
        enum_check("action_type", ApprovalActionType),
        enum_check("decision", ApprovalDecision),
        enum_check("from_status", WorkflowStatus, nullable=True),
        enum_check("to_status", WorkflowStatus, nullable=True),
        Index("ix_approval_actions_case_id", "case_id"),
    )

    case_id: Mapped[UUID] = mapped_column(ForeignKey("verification_cases.id", ondelete="RESTRICT"), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str | None] = mapped_column(String(32))
    remarks: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ReleaseEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "release_events"
    __table_args__ = (Index("ix_release_events_fdr_record_id", "fdr_record_id"),)

    case_id: Mapped[UUID] = mapped_column(ForeignKey("verification_cases.id", ondelete="RESTRICT"), nullable=False)
    fdr_record_id: Mapped[UUID] = mapped_column(ForeignKey("fdr_records.id", ondelete="RESTRICT"), nullable=False)
    recorded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    released_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    release_reference: Mapped[str | None] = mapped_column(String(160))
    remarks: Mapped[str | None] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
