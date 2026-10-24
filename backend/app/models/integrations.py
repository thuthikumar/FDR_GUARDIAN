"""Import synchronization run metadata."""

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.db.constraints import enum_check
from app.models.enums import SyncRunStatus


class IntegrationSyncRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "integration_sync_runs"
    __table_args__ = (
        enum_check("status", SyncRunStatus),
        CheckConstraint(
            "records_read >= 0 AND records_created >= 0 AND records_updated >= 0 AND records_skipped >= 0",
            name="record_counts_nonnegative",
        ),
    )

    source_name: Mapped[str] = mapped_column(String(120), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    records_read: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    records_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    records_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    records_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    errors_summary: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
