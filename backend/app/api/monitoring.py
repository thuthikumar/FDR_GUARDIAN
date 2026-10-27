"""Scoped alert centre and privileged maturity-monitoring controls."""

from datetime import date, datetime, time, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import require_permission
from app.core.config import app_timezone
from app.core.permissions import Permission
from app.db.session import get_session
from app.models.enums import AlertSeverity, AlertStatus, UserRole
from app.models.fdr import FDRRecord
from app.models.institutions import Institution
from app.models.monitoring import Alert, AuditEvent, MaturityRule, MonitoringJobRun
from app.models.users import User
from app.schemas.monitoring import (AlertDetail, AlertFdrSummary, AlertHistoryItem, AlertListItem, AlertPage,
    MaturityRuleSchema, MaturityRulesResponse, MonitoringRunPage, MonitoringRunRequest,
    MonitoringRunSummary, MonitoringSummary, ResolveAlertRequest, SafeAlertDetails)
from app.services.audit import write_audit_event
from app.services.monitoring import RuleBand, _append_history, evaluate_maturities, monitoring_aggregates, validate_rule_set

router = APIRouter(tags=["alerts and monitoring"])


def _scoped_alert_stmt(user: User):
    stmt = select(Alert, FDRRecord, Institution).join(FDRRecord, FDRRecord.id == Alert.fdr_record_id).join(Institution, Institution.id == FDRRecord.institution_id)
    if user.role == UserRole.INSTITUTION_ADMIN.value:
        if user.institution_id is None:
            stmt = stmt.where(Institution.id.is_(None))
        else:
            stmt = stmt.where(Institution.id == user.institution_id)
    return stmt


def _alert_access(session: Session, user: User, alert_id: UUID):
    row = session.execute(_scoped_alert_stmt(user).where(Alert.id == alert_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return row


def _safe_details(value: dict) -> SafeAlertDetails:
    allowed = {key: value[key] for key in ("days_remaining", "maturity_date", "thresholds_used", "evaluated_at", "reference_date", "legacy_seeded") if key in value}
    allowed["lifecycle"] = [{key: str(event[key]) for key in ("event", "at", "reason", "next_rule", "remarks") if key in event}
                             for event in value.get("lifecycle", []) if isinstance(event, dict)]
    return SafeAlertDetails.model_validate(allowed)


def _list_item(row) -> AlertListItem:
    alert, fdr, institution = row
    return AlertListItem(id=alert.id, alert_type=alert.alert_type, rule_key=alert.rule_key,
        severity=alert.severity, status=alert.status, explanation=alert.explanation, created_at=alert.created_at,
        fdr=AlertFdrSummary(record_id=fdr.id, internal_fdr_id=fdr.internal_fdr_id, fdr_number=fdr.fdr_number,
            bank_name=fdr.bank_name, maturity_date=fdr.maturity_date, record_status=fdr.record_status,
            institution_id=institution.id, institution_name=institution.institution_name))


@router.get("/alerts", response_model=AlertPage)
def list_alerts(severity: AlertSeverity | None = None, alert_type: str | None = Query(None, max_length=64),
    status: Literal["open", "acknowledged", "resolved", "superseded", "unresolved"] | None = None,
    rule_key: str | None = Query(None, max_length=80), institution_id: UUID | None = None, fdr_id: UUID | None = None,
    created_from: date | None = None, created_to: date | None = None, q: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
    sort_by: Literal["created_at", "severity", "status", "alert_type"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    user: User = Depends(require_permission(Permission.ALERT_READ)), session: Session = Depends(get_session)) -> AlertPage:
    stmt = _scoped_alert_stmt(user)
    if user.role != UserRole.INSTITUTION_ADMIN.value and institution_id:
        stmt = stmt.where(FDRRecord.institution_id == institution_id)
    if severity: stmt = stmt.where(Alert.severity == severity.value)
    if alert_type: stmt = stmt.where(Alert.alert_type == alert_type)
    if status == "unresolved": stmt = stmt.where(Alert.status.in_([AlertStatus.OPEN.value, AlertStatus.ACKNOWLEDGED.value]))
    elif status: stmt = stmt.where(Alert.status == status)
    if rule_key: stmt = stmt.where(Alert.rule_key == rule_key)
    if fdr_id: stmt = stmt.where(FDRRecord.id == fdr_id)
    if created_from: stmt = stmt.where(Alert.created_at >= datetime.combine(created_from, time.min, tzinfo=app_timezone()))
    if created_to: stmt = stmt.where(Alert.created_at < datetime.combine(created_to + timedelta(days=1), time.min, tzinfo=app_timezone()))
    if q:
        term = q.strip().replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(FDRRecord.internal_fdr_id.ilike(f"%{term}%", escape="\\"))
    total = int(session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()) ) or 0)
    column = {"created_at": Alert.created_at, "severity": Alert.severity, "status": Alert.status, "alert_type": Alert.alert_type}[sort_by]
    rows = session.execute(stmt.order_by(column.desc() if sort_order == "desc" else column.asc(), Alert.id).offset((page-1)*page_size).limit(page_size)).all()
    return AlertPage(items=[_list_item(row) for row in rows], total=total, page=page, page_size=page_size)


@router.get("/alerts/{alert_id}", response_model=AlertDetail)
def get_alert(alert_id: UUID, user: User = Depends(require_permission(Permission.ALERT_READ)),
              session: Session = Depends(get_session)) -> AlertDetail:
    alert, fdr, institution = _alert_access(session, user, alert_id)
    item = _list_item((alert, fdr, institution))
    lifecycle = _safe_details(alert.details or {}).lifecycle
    if not lifecycle:
        lifecycle = [AlertHistoryItem(event="created", at=alert.created_at.isoformat())]
    return AlertDetail(**item.model_dump(), details=_safe_details(alert.details or {}),
        acknowledged_at=alert.acknowledged_at, resolved_at=alert.resolved_at, reopened_at=alert.reopened_at,
        resolution_type=alert.resolution_type, resolution_remarks=alert.resolution_remarks, history=lifecycle)


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertDetail)
def acknowledge_alert(alert_id: UUID, request: Request,
    actor: User = Depends(require_permission(Permission.ALERT_MANAGE)), session: Session = Depends(get_session)) -> AlertDetail:
    alert, _, _ = _alert_access(session, actor, alert_id)
    if alert.status == AlertStatus.ACKNOWLEDGED.value:
        return get_alert(alert_id, actor, session)
    if alert.status != AlertStatus.OPEN.value:
        raise HTTPException(status_code=409, detail="Only open alerts can be acknowledged")
    now = datetime.now(app_timezone())
    alert.status = AlertStatus.ACKNOWLEDGED.value
    alert.acknowledged_by = actor.id
    alert.acknowledged_at = now
    alert.details = _append_history(alert.details or {}, "acknowledged", now)
    write_audit_event(session, request, action="alert_acknowledged", entity_type="alert", entity_id=alert.id,
        actor_id=actor.id, change_summary={"alert_type": alert.alert_type})
    session.commit()
    return get_alert(alert_id, actor, session)


@router.post("/alerts/{alert_id}/resolve", response_model=AlertDetail)
def resolve_alert(alert_id: UUID, body: ResolveAlertRequest, request: Request,
    actor: User = Depends(require_permission(Permission.ALERT_MANAGE)), session: Session = Depends(get_session)) -> AlertDetail:
    alert, _, _ = _alert_access(session, actor, alert_id)
    remarks = body.remarks.strip()
    if not remarks:
        raise HTTPException(status_code=422, detail="Resolution remarks are required")
    if alert.status not in (AlertStatus.OPEN.value, AlertStatus.ACKNOWLEDGED.value):
        raise HTTPException(status_code=409, detail="Only open or acknowledged alerts can be resolved")
    now = datetime.now(app_timezone())
    alert.status = AlertStatus.RESOLVED.value
    alert.resolved_at = now
    alert.resolved_by = actor.id
    alert.resolution_type = "manual"
    alert.resolution_remarks = remarks
    alert.details = _append_history(alert.details or {}, "resolved", now, remarks=remarks)
    write_audit_event(session, request, action="alert_resolved", entity_type="alert", entity_id=alert.id,
        actor_id=actor.id, change_summary={"alert_type": alert.alert_type, "remarks": remarks})
    session.commit()
    return get_alert(alert_id, actor, session)


@router.get("/monitoring/summary", response_model=MonitoringSummary)
def monitoring_summary(user: User = Depends(require_permission(Permission.ALERT_READ)),
                       session: Session = Depends(get_session)) -> MonitoringSummary:
    by_band, by_severity, by_status, upcoming = monitoring_aggregates(session, user)
    last = session.scalar(select(MonitoringJobRun).order_by(MonitoringJobRun.started_at.desc()))
    last_data = {"status": last.status, "started_at": last.started_at.isoformat(), "completed_at": last.completed_at.isoformat() if last.completed_at else None} if last else None
    return MonitoringSummary(counts_by_band=by_band, counts_by_severity=by_severity,
        counts_by_status=by_status, upcoming_maturities_by_band=upcoming, last_job_run=last_data)


@router.get("/monitoring/rules", response_model=MaturityRulesResponse)
def get_rules(user: User = Depends(require_permission(Permission.ALERT_READ)),
              session: Session = Depends(get_session)) -> MaturityRulesResponse:
    del user
    rows = session.scalars(select(MaturityRule).order_by(MaturityRule.min_days.nulls_first())).all()
    return MaturityRulesResponse(items=[MaturityRuleSchema.model_validate(row, from_attributes=True) for row in rows],
        demo_default_notice="These thresholds are demo defaults, not verified AICTE policy.")


@router.put("/monitoring/rules", response_model=MaturityRulesResponse)
def update_rules(items: list[MaturityRuleSchema], request: Request,
    actor: User = Depends(require_permission(Permission.MONITORING_CONFIGURE)), session: Session = Depends(get_session)) -> MaturityRulesResponse:
    if len({item.rule_key for item in items}) != len(items):
        raise HTTPException(status_code=422, detail="Maturity rule keys must be unique")
    try:
        proposed = validate_rule_set(RuleBand(i.rule_key, i.alert_type, i.label, i.min_days, i.max_days, i.severity, i.is_active) for i in items)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    if any(item.severity not in {value.value for value in AlertSeverity} for item in proposed):
        raise HTTPException(status_code=422, detail="A maturity rule contains an invalid severity")
    old = session.scalars(select(MaturityRule)).all()
    old_values = [MaturityRuleSchema.model_validate(row, from_attributes=True).model_dump() for row in old]
    by_key = {row.rule_key: row for row in old}
    if len(by_key) != len(proposed):
        raise HTTPException(status_code=422, detail="The complete existing maturity rule set must be supplied")
    for item in proposed:
        row = by_key.get(item.rule_key)
        if row is None:
            raise HTTPException(status_code=422, detail="Rule keys cannot be added or removed in this phase")
        for key in ("alert_type", "label", "min_days", "max_days", "severity", "is_active"):
            setattr(row, key, getattr(item, key))
    write_audit_event(session, request, action="maturity_rules_updated", entity_type="maturity_rules",
        entity_id=old[0].id, actor_id=actor.id, change_summary={"old_rules": old_values, "new_rules": [
            {"rule_key": item.rule_key, "alert_type": item.alert_type, "label": item.label, "min_days": item.min_days,
             "max_days": item.max_days, "severity": item.severity, "is_active": item.is_active} for item in proposed]})
    session.commit()
    return get_rules(actor, session)


def _run_response(row: MonitoringJobRun) -> MonitoringRunSummary:
    return MonitoringRunSummary(id=row.id, job_name=row.job_name, trigger=row.run_trigger, reference_date=row.reference_date,
        started_at=row.started_at, completed_at=row.completed_at, status=row.status, records_evaluated=row.records_evaluated,
        alerts_created=row.alerts_created, alerts_superseded=row.alerts_superseded, alerts_resolved=row.alerts_resolved,
        alerts_reopened=row.alerts_reopened, alerts_unchanged=row.alerts_unchanged, errors_summary=row.errors_summary or {})


@router.get("/monitoring/runs", response_model=MonitoringRunPage)
def list_runs(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(require_permission(Permission.MONITORING_RUN)), session: Session = Depends(get_session)) -> MonitoringRunPage:
    del user
    total = int(session.scalar(select(func.count()).select_from(MonitoringJobRun)) or 0)
    rows = session.scalars(select(MonitoringJobRun).order_by(MonitoringJobRun.started_at.desc()).offset((page-1)*page_size).limit(page_size)).all()
    return MonitoringRunPage(items=[_run_response(row) for row in rows], total=total, page=page, page_size=page_size)


@router.post("/monitoring/run", response_model=MonitoringRunSummary)
def run_monitoring(body: MonitoringRunRequest, request: Request,
    actor: User = Depends(require_permission(Permission.MONITORING_RUN)), session: Session = Depends(get_session)) -> MonitoringRunSummary:
    tz = app_timezone()
    reference = datetime.combine(body.reference_date, time.min, tzinfo=tz) if body.reference_date else datetime.now(tz)
    if reference.date() > datetime.now(tz).date() + timedelta(days=366):
        raise HTTPException(status_code=422, detail="Reference date cannot be more than 366 days in the future")
    return _run_response(evaluate_maturities(session, reference_datetime=reference, trigger="manual", triggered_by=actor.id, request=request))
