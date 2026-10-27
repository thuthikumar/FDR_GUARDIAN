"""Add maturity rules, alert lifecycle metadata, and monitoring runs."""

from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "5d6e7f8a9b10"
down_revision: Union[str, Sequence[str], None] = "c05c691acd14"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_fdr_records_record_status_valid"), "fdr_records", type_="check")
    op.create_check_constraint("record_status_valid", "fdr_records",
        "record_status IN ('draft', 'active', 'under_verification', 'discrepancy', 'matured', 'released', 'cancelled', 'closed')")

    op.create_table(
        "maturity_rules",
        sa.Column("rule_key", sa.String(80), nullable=False),
        sa.Column("alert_type", sa.String(64), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("min_days", sa.Integer(), nullable=True),
        sa.Column("max_days", sa.Integer(), nullable=True),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_maturity_rules"),
        sa.UniqueConstraint("rule_key", name="uq_maturity_rules_rule_key"),
        sa.CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')", name=op.f("ck_maturity_rules_severity_valid")),
        sa.CheckConstraint("min_days IS NULL OR max_days IS NULL OR min_days <= max_days", name=op.f("ck_maturity_rules_range_valid")),
    )
    defaults = [
        ("maturity_overdue_date_review", "maturity_overdue_date_review", "Overdue-date review", None, -1, "high"),
        ("maturity_urgent", "maturity_urgent", "Urgent", 0, 7, "high"),
        ("maturity_attention_required", "maturity_attention_required", "Attention required", 8, 30, "medium"),
        ("maturity_upcoming", "maturity_upcoming", "Upcoming", 31, 90, "low"),
        ("maturity_normal", "maturity_normal", "Normal", 91, None, "low"),
    ]
    for key, alert_type, label, low, high, severity in defaults:
        op.execute(sa.text("""INSERT INTO maturity_rules (id, rule_key, alert_type, label, min_days, max_days, severity, is_active)
            VALUES (:id, :key, :type, :label, :low, :high, :severity, true)""").bindparams(
                id=uuid4(), key=key, type=alert_type, label=label, low=low, high=high, severity=severity))

    op.add_column("alerts", sa.Column("rule_key", sa.String(80), nullable=True))
    op.add_column("alerts", sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("alerts", sa.Column("acknowledged_by", sa.Uuid(), nullable=True))
    op.add_column("alerts", sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("alerts", sa.Column("resolution_type", sa.String(16), nullable=True))
    op.add_column("alerts", sa.Column("resolution_remarks", sa.Text(), nullable=True))
    op.add_column("alerts", sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("alerts", sa.Column("source", sa.String(24), server_default="legacy_seed", nullable=False))
    op.add_column("alerts", sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_alerts_acknowledged_by_users", "alerts", "users", ["acknowledged_by"], ["id"], ondelete="RESTRICT")
    op.create_check_constraint("resolution_type_valid", "alerts", "resolution_type IS NULL OR resolution_type IN ('auto', 'manual')")
    op.create_check_constraint("source_valid", "alerts", "source IN ('system_rule', 'legacy_seed', 'manual', 'other')")
    # Adopt only the old seeded maturity warning into the new rule lifecycle. Other six
    # demo alerts remain intact as legacy rows and are never modified by the rule engine.
    op.execute("""UPDATE alerts SET source='system_rule', rule_key='maturity_upcoming',
        details=jsonb_build_object('legacy_seeded', true, 'maturity_date', f.maturity_date::text),
        last_evaluated_at=alerts.created_at FROM fdr_records f
        WHERE alerts.fdr_record_id=f.id AND alerts.alert_type='maturity_upcoming' AND alerts.status IN ('open','acknowledged')""")

    op.create_table(
        "monitoring_job_runs",
        sa.Column("job_name", sa.String(80), nullable=False),
        sa.Column("trigger", sa.String(16), nullable=False),
        sa.Column("reference_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("records_evaluated", sa.Integer(), server_default="0", nullable=False),
        sa.Column("alerts_created", sa.Integer(), server_default="0", nullable=False),
        sa.Column("alerts_superseded", sa.Integer(), server_default="0", nullable=False),
        sa.Column("alerts_resolved", sa.Integer(), server_default="0", nullable=False),
        sa.Column("alerts_reopened", sa.Integer(), server_default="0", nullable=False),
        sa.Column("alerts_unchanged", sa.Integer(), server_default="0", nullable=False),
        sa.Column("errors_summary", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("triggered_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_monitoring_job_runs"),
        sa.ForeignKeyConstraint(["triggered_by"], ["users.id"], name="fk_monitoring_job_runs_triggered_by_users", ondelete="RESTRICT"),
        sa.CheckConstraint("trigger IN ('scheduled', 'manual', 'cli')", name=op.f("ck_monitoring_job_runs_trigger_valid")),
    )
    op.create_index("ix_monitoring_job_runs_started_at", "monitoring_job_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_monitoring_job_runs_started_at", table_name="monitoring_job_runs")
    op.drop_table("monitoring_job_runs")
    op.drop_constraint(op.f("ck_alerts_source_valid"), "alerts", type_="check")
    op.drop_constraint(op.f("ck_alerts_resolution_type_valid"), "alerts", type_="check")
    op.drop_constraint("fk_alerts_acknowledged_by_users", "alerts", type_="foreignkey")
    for column in ("last_evaluated_at", "source", "reopened_at", "resolution_remarks", "resolution_type", "acknowledged_at", "acknowledged_by", "details", "rule_key"):
        op.drop_column("alerts", column)
    op.drop_table("maturity_rules")
    op.drop_constraint(op.f("ck_fdr_records_record_status_valid"), "fdr_records", type_="check")
    op.create_check_constraint("record_status_valid", "fdr_records",
        "record_status IN ('draft', 'active', 'matured', 'released', 'cancelled')")
