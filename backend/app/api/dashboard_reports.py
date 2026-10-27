"""Read-only dashboard and report endpoints with backend enforced scope."""

import csv
import io
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.dependencies import require_permission
from app.core.permissions import Permission, permissions_for_role
from app.core.config import maturity_thresholds
from app.db.session import get_session
from app.models.enums import AlertStatus, FDRRecordStatus, UserRole, WorkflowStatus
from app.models.fdr import FDRRecord
from app.models.institutions import Institution
from app.models.monitoring import Alert
from app.models.users import User
from app.models.workflow import VerificationCase
from app.schemas.reports import (CountPoint, DashboardCharts, DashboardSummary, InstitutionSummaryPage,
    InstitutionSummaryRow, MaturityReportPage, MaturityReportRow)
from app.services.audit import write_audit_event

router = APIRouter(tags=["dashboard and reports"])
TZ = ZoneInfo("Asia/Kolkata")


def maturity_bucket(days: int, *, upcoming_days: int = 90, attention_days: int = 30,
                    urgent_days: int = 7) -> str:
    if days < 0:
        return "overdue-date review"
    if days <= urgent_days:
        return "urgent"
    if days <= attention_days:
        return "attention"
    if days <= upcoming_days:
        return "upcoming"
    return "normal"


def configured_thresholds() -> tuple[int, int, int]:
    return maturity_thresholds()


def _today(now: datetime | None = None) -> date:
    return (now or datetime.now(TZ)).astimezone(TZ).date()


def _csv_safe(value: str) -> str:
    return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value


def _scope(statement, user: User):
    if user.role == UserRole.INSTITUTION_ADMIN.value:
        if user.institution_id is None:
            return statement.where(FDRRecord.institution_id == None)  # noqa: E711
        statement = statement.where(FDRRecord.institution_id == user.institution_id)
    return statement


def _count(session: Session, statement) -> int:
    return int(session.scalar(statement) or 0)


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(user: User = Depends(require_permission(Permission.REPORT_READ)),
                     session: Session = Depends(get_session)) -> DashboardSummary:
    today = _today()
    base = _scope(select(FDRRecord.id), user).subquery()
    scoped_ids = select(base.c.id)
    active = _count(session, select(func.count()).select_from(FDRRecord).where(FDRRecord.id.in_(scoped_ids), FDRRecord.record_status == FDRRecordStatus.ACTIVE.value))
    total = _count(session, select(func.count()).select_from(base))
    upcoming = _count(session, select(func.count()).select_from(FDRRecord).where(FDRRecord.id.in_(scoped_ids), FDRRecord.maturity_date >= today, FDRRecord.maturity_date <= today + timedelta(days=90)))
    overdue = _count(session, select(func.count()).select_from(FDRRecord).where(FDRRecord.id.in_(scoped_ids), FDRRecord.maturity_date < today))
    pending_statuses = [WorkflowStatus.SUBMITTED.value, WorkflowStatus.UNDER_REVIEW.value, WorkflowStatus.MORE_INFORMATION_REQUIRED.value, WorkflowStatus.PENDING_APPROVAL.value, WorkflowStatus.RELEASE_PENDING.value]
    pending = _count(session, select(func.count()).select_from(VerificationCase).where(VerificationCase.fdr_record_id.in_(scoped_ids), VerificationCase.status.in_(pending_statuses)))
    unresolved = _count(session, select(func.count()).select_from(Alert).where(Alert.fdr_record_id.in_(scoped_ids), Alert.status.in_([AlertStatus.OPEN.value, AlertStatus.ACKNOWLEDGED.value])))
    inst_stmt = select(func.count()).select_from(Institution)
    if user.role == UserRole.INSTITUTION_ADMIN.value:
        inst_stmt = inst_stmt.where(Institution.id == user.institution_id)
    return DashboardSummary(total_institutions=_count(session, inst_stmt), total_fdr_records=total, active_records=active,
        upcoming_maturities=upcoming, overdue_date_review=overdue, pending_verification_cases=pending, unresolved_alerts=unresolved)


@router.get("/dashboard/charts", response_model=DashboardCharts)
def dashboard_charts(user: User = Depends(require_permission(Permission.REPORT_READ)),
                     session: Session = Depends(get_session)) -> DashboardCharts:
    today = _today()
    scoped = _scope(select(FDRRecord), user).subquery()
    statuses = {label: count for label, count in session.execute(select(scoped.c.record_status, func.count()).group_by(scoped.c.record_status)).all()}
    records_by_status = [CountPoint(label=status.value, count=int(statuses.get(status.value, 0))) for status in FDRRecordStatus]
    month_year, month_number = func.extract("year", scoped.c.maturity_date), func.extract("month", scoped.c.maturity_date)
    month_rows = session.execute(select(month_year, month_number, func.count()).where(
        scoped.c.maturity_date >= today, scoped.c.maturity_date < today + timedelta(days=366)).group_by(month_year, month_number)).all()
    month_counts = {f"{int(year):04d}-{int(month):02d}": int(count) for year, month, count in month_rows}
    month_points = []
    for offset in range(12):
        year, month0 = divmod((today.month - 1) + offset, 12)
        month_points.append(CountPoint(label=f"{today.year + year}-{month0 + 1:02d}", count=month_counts.get(f"{today.year + year}-{month0 + 1:02d}", 0)))
    distribution = session.execute(select(Institution.id, Institution.institution_name, func.count(scoped.c.id)).join(scoped, scoped.c.institution_id == Institution.id).group_by(Institution.id, Institution.institution_name).order_by(func.count(scoped.c.id).desc(), Institution.institution_name)).all()
    if user.role == UserRole.INSTITUTION_ADMIN.value:
        institution_points = [CountPoint(id=identity, label=name, count=int(count)) for identity, name, count in distribution[:1]]
    else:
        top = distribution[:10]
        other_count = sum(int(count) for _, count in distribution[10:])
        institution_points = [CountPoint(id=identity, label=name, count=int(count)) for identity, name, count in top]
        if other_count:
            institution_points.append(CountPoint(label="Others", count=other_count))
    case_rows = session.execute(select(VerificationCase.status, func.count()).join(scoped, scoped.c.id == VerificationCase.fdr_record_id).group_by(VerificationCase.status)).all()
    case_counts = dict(case_rows)
    return DashboardCharts(records_by_status=records_by_status, maturities_by_month=month_points,
        institution_distribution=institution_points, cases_by_status=[CountPoint(label=s.value, count=int(case_counts.get(s.value, 0))) for s in WorkflowStatus])


def _summary_query(user: User, today: date):
    stmt = select(Institution.id, Institution.institution_name, func.count(FDRRecord.id),
        func.count(case((FDRRecord.record_status == FDRRecordStatus.ACTIVE.value, 1))),
        func.coalesce(func.sum(FDRRecord.amount), Decimal("0")),
        func.min(case((FDRRecord.maturity_date >= today, FDRRecord.maturity_date), else_=None)))\
        .outerjoin(FDRRecord, FDRRecord.institution_id == Institution.id).group_by(Institution.id, Institution.institution_name)
    if user.role == UserRole.INSTITUTION_ADMIN.value:
        stmt = stmt.where(Institution.id == user.institution_id)
    return stmt


@router.get("/reports/institution-summary", response_model=InstitutionSummaryPage)
def institution_summary(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
    format: Literal["json", "csv"] = "json", request: Request = None,
    user: User = Depends(require_permission(Permission.REPORT_READ)), session: Session = Depends(get_session)) -> InstitutionSummaryPage:
    if format == "csv" and Permission.REPORT_EXPORT not in permissions_for_role(user.role):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Insufficient permission")
    stmt = _summary_query(user, _today()).order_by(Institution.institution_name)
    rows = session.execute(stmt).all() if format == "csv" else session.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    total = _count(session, select(func.count()).select_from(Institution).where(Institution.id == user.institution_id) if user.role == UserRole.INSTITUTION_ADMIN.value else select(func.count()).select_from(Institution))
    items = [InstitutionSummaryRow(institution_id=r[0], institution_name=r[1], total_fdrs=r[2], active_fdrs=r[3], total_principal=r[4], nearest_upcoming_maturity=r[5]) for r in rows]
    if format == "csv":
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["Generated at", datetime.now(TZ).isoformat()]); writer.writerow(["Data source", "synthetic demo"])
        writer.writerow(["Institution", "Total FDRs", "Active FDRs", "Total principal (INR)", "Nearest upcoming maturity"])
        for row in items:
            values = [row.institution_name, str(row.total_fdrs), str(row.active_fdrs), str(row.total_principal), row.nearest_upcoming_maturity.isoformat() if row.nearest_upcoming_maturity else ""]
            writer.writerow([_csv_safe(v) for v in values])
        write_audit_event(session, request, action="report_csv_exported", entity_type="report", entity_id=uuid4(), actor_id=user.id,
            change_summary={"report_name": "institution-summary", "filters": {}, "row_count": len(items)})
        session.commit()
        return Response(content="\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=institution-summary.csv"})
    return InstitutionSummaryPage(items=items, total=total, page=page, page_size=page_size)


def _maturity_stmt(user: User, today: date, maturity_from, maturity_to, institution_id, bucket):
    stmt = select(FDRRecord, Institution.institution_name).join(Institution, Institution.id == FDRRecord.institution_id)
    if user.role == UserRole.INSTITUTION_ADMIN.value:
        stmt = stmt.where(FDRRecord.institution_id == user.institution_id)
    elif institution_id:
        stmt = stmt.where(FDRRecord.institution_id == institution_id)
    if maturity_from:
        stmt = stmt.where(FDRRecord.maturity_date >= maturity_from)
    if maturity_to:
        stmt = stmt.where(FDRRecord.maturity_date <= maturity_to)
    if bucket:
        urgent_days, attention_days, upcoming_days = configured_thresholds()
        ranges = {"overdue-date review": FDRRecord.maturity_date < today, "urgent": FDRRecord.maturity_date.between(today, today + timedelta(days=urgent_days)),
          "attention": FDRRecord.maturity_date.between(today + timedelta(days=urgent_days+1), today + timedelta(days=attention_days)),
          "upcoming": FDRRecord.maturity_date.between(today + timedelta(days=attention_days+1), today + timedelta(days=upcoming_days)),
          "normal": FDRRecord.maturity_date > today + timedelta(days=upcoming_days)}
        stmt = stmt.where(ranges[bucket])
    return stmt


@router.get("/reports/maturities", response_model=MaturityReportPage)
def maturities(maturity_from: date | None = None, maturity_to: date | None = None,
    bucket: Literal["overdue-date review", "urgent", "attention", "upcoming", "normal"] | None = None,
    institution_id: UUID | None = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
    sort_by: Literal["maturity_date", "amount", "institution_name", "record_status"] = "maturity_date",
    sort_order: Literal["asc", "desc"] = "asc", format: Literal["json", "csv"] = "json",
    request: Request = None, user: User = Depends(require_permission(Permission.REPORT_READ)),
    session: Session = Depends(get_session)):
    if format == "csv" and Permission.REPORT_EXPORT not in permissions_for_role(user.role):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Insufficient permission")
    if maturity_from and maturity_to and maturity_from > maturity_to:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="maturity_from must not be after maturity_to")
    target = institution_id
    today = _today()
    stmt = _maturity_stmt(user, today, maturity_from, maturity_to, target, bucket)
    sort_cols = {"maturity_date": FDRRecord.maturity_date, "amount": FDRRecord.amount, "institution_name": Institution.institution_name, "record_status": FDRRecord.record_status}
    stmt = stmt.order_by(sort_cols[sort_by].desc() if sort_order == "desc" else sort_cols[sort_by].asc())
    total = _count(session, select(func.count()).select_from(stmt.order_by(None).subquery()))
    if format == "csv":
        rows = session.execute(stmt).all()
    else:
        rows = session.execute(stmt.offset((page-1)*page_size).limit(page_size)).all()
    def to_row(r):
        fdr, name = r
        return MaturityReportRow(record_id=fdr.id, institution_id=fdr.institution_id, institution_name=name,
            internal_fdr_id=fdr.internal_fdr_id, fdr_number=fdr.fdr_number, bank_name=fdr.bank_name,
            amount=fdr.amount, currency=fdr.currency, maturity_date=fdr.maturity_date, record_status=fdr.record_status,
            bucket=maturity_bucket((fdr.maturity_date-today).days, upcoming_days=configured_thresholds()[0], attention_days=configured_thresholds()[1], urgent_days=configured_thresholds()[2]))
    if format == "csv":
        selected = [to_row(r) for r in rows]
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        generated = datetime.now(TZ).isoformat()
        writer.writerow(["Generated at", generated]); writer.writerow(["Data source", "synthetic demo"])
        headers = ["Institution", "Internal FDR ID", "FDR number", "Bank", "Principal", "Currency", "Maturity date", "Record status", "Maturity bucket"]
        writer.writerow(headers)
        for row in selected:
            vals = [row.institution_name, row.internal_fdr_id, row.fdr_number, row.bank_name, str(row.amount), row.currency, row.maturity_date.isoformat(), row.record_status, row.bucket]
            writer.writerow([_csv_safe(value) for value in vals])
        write_audit_event(session, request, action="report_csv_exported", entity_type="report", entity_id=uuid4(), actor_id=user.id,
            change_summary={"report_name": "maturities", "filters": {"maturity_from": str(maturity_from) if maturity_from else None, "maturity_to": str(maturity_to) if maturity_to else None, "bucket": bucket, "institution_id": str(target) if target else None}, "row_count": len(selected)})
        session.commit()
        return Response(content="\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=maturities.csv"})
    return MaturityReportPage(items=[to_row(r) for r in rows], total=total, page=page, page_size=page_size)
