"""Maturity-band evaluation and owned alert lifecycle management."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from datetime import date, datetime, time
from types import SimpleNamespace
from typing import Iterable
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import app_timezone
from app.models.enums import AlertStatus, FDRRecordStatus
from app.models.fdr import FDRRecord
from app.models.monitoring import Alert, AuditEvent, MaturityRule, MonitoringJobRun
from app.models.users import User
from app.services.audit import write_audit_event

logger = logging.getLogger("fdr_guardian.monitoring")
LOCK_KEY = 0x4644524D
ELIGIBLE_STATUSES = {"active", "under_verification", "discrepancy"}
CLOSED_STATUSES = {FDRRecordStatus.MATURED.value, FDRRecordStatus.RELEASED.value,
                   FDRRecordStatus.CANCELLED.value, FDRRecordStatus.CLOSED.value}
OWNED_TYPES = {"maturity_upcoming", "maturity_attention_required", "maturity_urgent", "maturity_overdue_date_review"}


@dataclass(frozen=True)
class RuleBand:
    rule_key: str
    alert_type: str
    label: str
    min_days: int | None
    max_days: int | None
    severity: str
    is_active: bool = True


DEFAULT_RULES = (
    RuleBand("maturity_overdue_date_review", "maturity_overdue_date_review", "Overdue-date review", None, -1, "high"),
    RuleBand("maturity_urgent", "maturity_urgent", "Urgent", 0, 7, "high"),
    RuleBand("maturity_attention_required", "maturity_attention_required", "Attention required", 8, 30, "medium"),
    RuleBand("maturity_upcoming", "maturity_upcoming", "Upcoming", 31, 90, "low"),
    RuleBand("maturity_normal", "maturity_normal", "Normal", 91, None, "low"),
)


def ensure_default_maturity_rules(session: Session) -> None:
    if session.scalar(select(MaturityRule.id).limit(1)) is not None:
        return
    for rule in DEFAULT_RULES:
        session.add(MaturityRule(rule_key=rule.rule_key, alert_type=rule.alert_type, label=rule.label,
            min_days=rule.min_days, max_days=rule.max_days, severity=rule.severity, is_active=True))
    session.flush()


def validate_rule_set(rules: Iterable[RuleBand]) -> list[RuleBand]:
    active = sorted((rule for rule in rules if rule.is_active), key=lambda item: -10**12 if item.min_days is None else item.min_days)
    if len(active) < 2:
        raise ValueError("At least two active maturity rules are required")
    if active[0].min_days is not None or active[0].max_days != -1:
        raise ValueError("The overdue-date rule must cover all negative days")
    for rule in active[1:]:
        if rule.min_days is None or rule.min_days < 0:
            raise ValueError("Active maturity rule bounds must be non-negative, except the overdue band")
        if rule.max_days is not None and rule.max_days < rule.min_days:
            raise ValueError("Maturity rule has a negative range")
    if sum(rule.max_days is None for rule in active) != 1 or active[-1].max_days is not None:
        raise ValueError("Exactly one open-ended top maturity band is required")
    for previous, current in zip(active, active[1:]):
        if previous.max_days is None or current.min_days != previous.max_days + 1:
            raise ValueError("Maturity rules must be ordered, contiguous, and non-overlapping")
    return active


def select_rule_band(rules: Iterable[RuleBand], days_remaining: int) -> RuleBand:
    ordered = validate_rule_set(rules)
    for rule in ordered:
        if (rule.min_days is None or days_remaining >= rule.min_days) and (rule.max_days is None or days_remaining <= rule.max_days):
            return rule
    raise ValueError("No maturity rule covers the requested day count")


def _rules(session: Session) -> list[RuleBand]:
    rows = session.scalars(select(MaturityRule).order_by(MaturityRule.min_days.nulls_first())).all()
    return validate_rule_set(RuleBand(r.rule_key, r.alert_type, r.label, r.min_days, r.max_days, r.severity, r.is_active) for r in rows)


def monitoring_aggregates(session: Session, user: User, today: date | None = None) -> tuple[dict[str, int], dict[str, int], dict[str, int], dict[str, int]]:
    """Shared band and unresolved-alert counts for Dashboard and Alert Centre."""
    alert_stmt = select(Alert, FDRRecord.institution_id).join(FDRRecord, FDRRecord.id == Alert.fdr_record_id)
    record_stmt = select(FDRRecord).where(FDRRecord.record_status.in_(ELIGIBLE_STATUSES))
    if user.role == "institution_admin":
        alert_stmt = alert_stmt.where(FDRRecord.institution_id == user.institution_id)
        record_stmt = record_stmt.where(FDRRecord.institution_id == user.institution_id)
    by_band: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for alert, _institution_id in session.execute(alert_stmt).all():
        band = alert.rule_key or alert.alert_type
        by_band[band] = by_band.get(band, 0) + 1
        by_severity[alert.severity] = by_severity.get(alert.severity, 0) + 1
        by_status[alert.status] = by_status.get(alert.status, 0) + 1
    active_rules = _rules(session)
    reference_date = today or datetime.now(app_timezone()).date()
    upcoming = {rule.rule_key: 0 for rule in active_rules}
    for record in session.scalars(record_stmt).all():
        rule = select_rule_band(active_rules, (record.maturity_date - reference_date).days)
        upcoming[rule.rule_key] += 1
    return by_band, by_severity, by_status, upcoming


def _append_history(details: dict, event: str, when: datetime, **extra) -> dict:
    value = dict(details or {})
    lifecycle = list(value.get("lifecycle", []))
    lifecycle.append({"event": event, "at": when.isoformat(), **extra})
    value["lifecycle"] = lifecycle
    return value


def _explanation(days: int, maturity: date, rule: RuleBand) -> str:
    date_text = maturity.isoformat()
    if days < 0:
        return f"Stored maturity date was {abs(days)} days ago ({date_text}); overdue-date review is suggested per demo rule."
    return f"Stored maturity date is {days} days away ({date_text}). {rule.label} per demo rule."


def _snapshot_details(rule: RuleBand, maturity: date, days: int, now: datetime, reference_date: date) -> dict:
    return {"days_remaining": days, "maturity_date": maturity.isoformat(),
            "thresholds_used": {"min_days": rule.min_days, "max_days": rule.max_days},
            "evaluated_at": now.isoformat(), "reference_date": reference_date.isoformat()}


def _auto_resolve(alert: Alert, now: datetime, reason: str, counts: dict[str, int]) -> None:
    alert.status = AlertStatus.RESOLVED.value
    alert.resolved_at = now
    alert.resolved_by = None
    alert.resolution_type = "auto"
    alert.resolution_remarks = reason
    alert.details = _append_history(alert.details, "auto_resolved", now, reason=reason)
    counts["alerts_resolved"] += 1


def _evaluate_record(session: Session, record: FDRRecord, rules: list[RuleBand], now: datetime,
                     reference_date: date, counts: dict[str, int]) -> None:
    owned = session.scalars(select(Alert).where(Alert.fdr_record_id == record.id, Alert.source == "system_rule", Alert.alert_type.in_(OWNED_TYPES)).order_by(Alert.created_at.desc())).all()
    active = [item for item in owned if item.status in (AlertStatus.OPEN.value, AlertStatus.ACKNOWLEDGED.value)]
    eligible = record.record_status in ELIGIBLE_STATUSES
    if not eligible:
        reason = "Record is no longer eligible for maturity monitoring."
        for item in active:
            _auto_resolve(item, now, reason, counts)
        return

    days = (record.maturity_date - reference_date).days
    rule = select_rule_band(rules, days)
    if rule.alert_type == "maturity_normal":
        for item in active:
            _auto_resolve(item, now, "Stored maturity date is outside alert bands.", counts)
        return

    current = next((item for item in active if item.rule_key == rule.rule_key), None)
    if current:
        details = dict(current.details or {})
        details.update(_snapshot_details(rule, record.maturity_date, days, now, reference_date))
        current.details = details
        current.explanation = _explanation(days, record.maturity_date, rule)
        current.last_evaluated_at = now
        counts["alerts_unchanged"] += 1
        return

    for item in active:
        item.status = "superseded"
        item.resolved_at = now
        item.resolution_type = "auto"
        item.resolution_remarks = "Superseded because a different maturity band now applies."
        item.details = _append_history(item.details, "superseded", now, next_rule=rule.rule_key)
        counts["alerts_superseded"] += 1

    maturity_snapshot = record.maturity_date.isoformat()
    same_rule = [item for item in owned if item.rule_key == rule.rule_key]
    manual_same_snapshot = next((item for item in owned if item.status == AlertStatus.RESOLVED.value
        and item.resolution_type == "manual" and (item.details or {}).get("maturity_date") == maturity_snapshot), None)
    if manual_same_snapshot:
        counts["alerts_unchanged"] += 1
        return
    auto_same_snapshot = next((item for item in same_rule if item.status == AlertStatus.RESOLVED.value
        and item.resolution_type == "auto" and (item.details or {}).get("maturity_date") == maturity_snapshot), None)
    details = _snapshot_details(rule, record.maturity_date, days, now, reference_date)
    if auto_same_snapshot:
        auto_same_snapshot.status = AlertStatus.OPEN.value
        auto_same_snapshot.resolved_at = None
        auto_same_snapshot.resolved_by = None
        auto_same_snapshot.resolution_type = None
        auto_same_snapshot.resolution_remarks = None
        auto_same_snapshot.reopened_at = now
        auto_same_snapshot.last_evaluated_at = now
        refreshed = dict(auto_same_snapshot.details or {})
        refreshed.update(details)
        auto_same_snapshot.details = _append_history(refreshed, "reopened", now)
        auto_same_snapshot.explanation = _explanation(days, record.maturity_date, rule)
        counts["alerts_reopened"] += 1
        return

    # A migrated legacy open maturity alert may already occupy the unique key.
    # It was explicitly adopted by the migration; normal idempotent update follows.
    session.add(Alert(fdr_record_id=record.id, alert_type=rule.alert_type, rule_key=rule.rule_key,
        severity=rule.severity, explanation=_explanation(days, record.maturity_date, rule), status=AlertStatus.OPEN.value,
        source="system_rule", details=_append_history(details, "created", now), last_evaluated_at=now))
    counts["alerts_created"] += 1


def _audit_run(session: Session, run: MonitoringJobRun, actor_id, request=None) -> None:
    req = request or SimpleNamespace(state=SimpleNamespace(request_id=None))
    write_audit_event(session, req, action="monitoring_run_completed", entity_type="monitoring_job_run",
        entity_id=run.id, actor_id=actor_id, change_summary={
            "run_status": run.status, "records_evaluated": run.records_evaluated,
            "alerts_created": run.alerts_created, "alerts_superseded": run.alerts_superseded,
            "alerts_resolved": run.alerts_resolved, "alerts_reopened": run.alerts_reopened,
            "alerts_unchanged": run.alerts_unchanged, "error_count": len((run.errors_summary or {}).get("errors", [])),
        })


def evaluate_maturities(session: Session, *, reference_datetime: datetime | None = None,
                        trigger: str = "manual", triggered_by=None, request=None) -> MonitoringJobRun:
    """Run one idempotent evaluation. PostgreSQL session advisory lock serialises workers."""
    tz = app_timezone()
    now = reference_datetime.astimezone(tz) if reference_datetime else datetime.now(tz)
    ref_date = now.date()
    run = MonitoringJobRun(job_name="maturity_monitoring", run_trigger=trigger,
        reference_date=now, started_at=now, status="running", triggered_by=triggered_by, errors_summary={})
    session.add(run)
    session.flush()
    acquired = bool(session.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": LOCK_KEY}))
    if not acquired:
        run.status = "skipped_locked"
        run.completed_at = now
        _audit_run(session, run, triggered_by, request)
        session.commit()
        logger.info("monitoring_run_finished", extra={"run_id": str(run.id), "status": run.status})
        return run

    logger.info("monitoring_run_started", extra={"run_id": str(run.id), "trigger": trigger, "reference_date": ref_date.isoformat()})
    counts = {"alerts_created": 0, "alerts_superseded": 0, "alerts_resolved": 0, "alerts_reopened": 0, "alerts_unchanged": 0}
    errors: list[dict[str, str]] = []
    try:
        rules = _rules(session)
        records = session.scalars(select(FDRRecord).order_by(FDRRecord.id)).all()
        for record in records:
            record_counts = dict.fromkeys(counts, 0)
            try:
                with session.begin_nested():
                    _evaluate_record(session, record, rules, now, ref_date, record_counts)
                    session.flush()
                run.records_evaluated += 1
                for key, value in record_counts.items():
                    counts[key] += value
            except Exception as exc:  # isolate one problematic record
                # begin_nested rolls back only this record's savepoint.
                for key in counts:
                    record_counts[key] = 0
                errors.append({"record_id": str(record.id), "error": type(exc).__name__})
                logger.error("monitoring_record_failed", extra={"record_id": str(record.id), "run_id": str(run.id), "error_type": type(exc).__name__})
        run.status = "partial_failure" if errors else "success"
        run.errors_summary = {"errors": errors}
    except Exception as exc:
        errors.append({"error": type(exc).__name__})
        run.status = "failed"
        run.errors_summary = {"errors": errors}
    finally:
        run.completed_at = now
        for key, value in counts.items():
            setattr(run, key, value)
        _audit_run(session, run, triggered_by, request)
        session.commit()
        logger.info("monitoring_run_finished", extra={"run_id": str(run.id), "status": run.status,
            "records_evaluated": run.records_evaluated, "alerts_created": run.alerts_created,
            "alerts_superseded": run.alerts_superseded, "alerts_resolved": run.alerts_resolved,
            "alerts_reopened": run.alerts_reopened})
    return run


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Run maturity monitoring using synthetic demo rules")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--reference-date", type=date.fromisoformat)
    args = parser.parse_args()
    from app.db.session import make_session_factory
    session = make_session_factory()()
    try:
        dt = datetime.combine(args.reference_date, time.min, tzinfo=app_timezone()) if args.reference_date else None
        result = evaluate_maturities(session, reference_datetime=dt, trigger="cli")
        print(f"Monitoring {result.status}: evaluated={result.records_evaluated} created={result.alerts_created} superseded={result.alerts_superseded} resolved={result.alerts_resolved} reopened={result.alerts_reopened} unchanged={result.alerts_unchanged}")
    finally:
        session.close()


if __name__ == "__main__":
    _cli()
