"""Alerts, notifications, and append-only audit events."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.constraints import enum_check
from app.models.enums import AlertSeverity, AlertStatus, NotificationType


class Alert(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint("resolution_type IS NULL OR resolution_type IN ('auto', 'manual')", name="resolution_type_valid"),
        CheckConstraint("source IN ('system_rule', 'legacy_seed', 'manual', 'other')", name="source_valid"),
        enum_check("status", AlertStatus),
        enum_check("severity", AlertSeverity),
        Index("ix_alerts_fdr_record_id", "fdr_record_id"),
        Index("ix_alerts_status", "status"),
        Index(
            "uq_alerts_one_active_type_per_fdr",
            "fdr_record_id",
            "alert_type",
            unique=True,
            postgresql_where=text("status IN ('open', 'acknowledged')"),
        ),
    )

    fdr_record_id: Mapped[UUID] = mapped_column(ForeignKey("fdr_records.id", ondelete="RESTRICT"), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    rule_key: Mapped[str | None] = mapped_column(String(80))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    acknowledged_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_type: Mapped[str | None] = mapped_column(String(16))
    resolution_remarks: Mapped[str | None] = mapped_column(Text)
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(24), nullable=False, default="legacy_seed", server_default="legacy_seed")
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MaturityRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "maturity_rules"
    __table_args__ = (
        CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')", name="severity_valid"),
        CheckConstraint("min_days IS NULL OR max_days IS NULL OR min_days <= max_days", name="range_valid"),
    )

    rule_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    min_days: Mapped[int | None] = mapped_column(Integer)
    max_days: Mapped[int | None] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class MonitoringJobRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "monitoring_job_runs"
    __table_args__ = (
        CheckConstraint("trigger IN ('scheduled', 'manual', 'cli')", name="trigger_valid"),
        Index("ix_monitoring_job_runs_started_at", "started_at"),
    )

    job_name: Mapped[str] = mapped_column(String(80), nullable=False)
    run_trigger: Mapped[str] = mapped_column("trigger", String(16), nullable=False)
    reference_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    records_evaluated: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    alerts_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    alerts_superseded: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    alerts_resolved: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    alerts_reopened: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    alerts_unchanged: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    errors_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    triggered_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class Notification(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (enum_check("notification_type", NotificationType), Index("ix_notifications_recipient_user_id", "recipient_user_id"))

    recipient_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    related_record_id: Mapped[UUID | None] = mapped_column()
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_entity", "entity_type", "entity_id"),
        Index("ix_audit_events_timestamp", "timestamp"),
    )

    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    correlation_id: Mapped[str | None] = mapped_column(String(120))
    change_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
