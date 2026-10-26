"""FDR registry endpoints with institution isolation and transactional audit history."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import require_permission
from app.core.permissions import Permission
from app.db.session import get_session
from app.models.enums import FDRRecordStatus, UserRole, VerificationStatus
from app.models.fdr import FDRRecord
from app.models.institutions import Institution
from app.models.monitoring import AuditEvent
from app.models.users import User
from app.schemas.fdrs import FDRCreate, FDRHistoryItem, FDRPage, FDRPatch, FDRResponse, FDRStatusChange
from app.services.audit import write_audit_event
from app.services.institution_access import scope_fdr_query


router = APIRouter(prefix="/fdrs", tags=["FDR registry"])

STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    FDRRecordStatus.DRAFT.value: frozenset({FDRRecordStatus.ACTIVE.value, FDRRecordStatus.CANCELLED.value}),
    FDRRecordStatus.ACTIVE.value: frozenset({FDRRecordStatus.MATURED.value, FDRRecordStatus.CANCELLED.value}),
    FDRRecordStatus.MATURED.value: frozenset({FDRRecordStatus.RELEASED.value}),
    FDRRecordStatus.RELEASED.value: frozenset(),
    FDRRecordStatus.CANCELLED.value: frozenset(),
}
EDITABLE_FIELDS = ("bank_name", "branch_name", "fdr_number", "amount", "currency", "issue_date", "maturity_date")
HISTORY_FIELDS = frozenset({"fdr_number", "bank_name", "branch_name", "issue_date", "maturity_date", "amount", "currency", "record_status"})


def _response(record: FDRRecord) -> FDRResponse:
    return FDRResponse(
        id=record.id,
        institution_id=record.institution_id,
        internal_fdr_id=record.internal_fdr_id,
        bank_name=record.bank_name,
        branch_name=record.branch_name,
        fdr_number=record.fdr_number,
        amount=record.amount,
        currency=record.currency,
        issue_date=record.issue_date,
        maturity_date=record.maturity_date,
        record_status=record.record_status,
        verification_status=record.verification_status,
        source_system=record.source_system,
        is_synthetic=record.is_synthetic,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    return value


def _escaped_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _visible_record(session: Session, user: User, record_id: UUID) -> FDRRecord:
    record = session.scalar(scope_fdr_query(select(FDRRecord), user).where(FDRRecord.id == record_id))
    if record is None:
        raise HTTPException(status_code=404, detail="FDR record not found")
    return record


@router.get("", response_model=FDRPage)
def list_fdrs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    institution_id: UUID | None = None,
    record_status: FDRRecordStatus | None = None,
    verification_status: VerificationStatus | None = None,
    maturity_from: date | None = None,
    maturity_to: date | None = None,
    q: str | None = Query(default=None, max_length=200),
    sort_by: Literal["internal_fdr_id", "bank_name", "fdr_number", "amount", "issue_date", "maturity_date", "record_status", "updated_at"] = "maturity_date",
    sort_order: Literal["asc", "desc"] = "asc",
    user: User = Depends(require_permission(Permission.FDR_READ)),
    session: Session = Depends(get_session),
) -> FDRPage:
    if maturity_from and maturity_to and maturity_to < maturity_from:
        raise HTTPException(status_code=422, detail="maturity_to must be on or after maturity_from")
    statement = scope_fdr_query(select(FDRRecord), user)
    if institution_id and user.role != UserRole.INSTITUTION_ADMIN.value:
        statement = statement.where(FDRRecord.institution_id == institution_id)
    if record_status:
        statement = statement.where(FDRRecord.record_status == record_status.value)
    if verification_status:
        statement = statement.where(FDRRecord.verification_status == verification_status.value)
    if maturity_from:
        statement = statement.where(FDRRecord.maturity_date >= maturity_from)
    if maturity_to:
        statement = statement.where(FDRRecord.maturity_date <= maturity_to)
    if q:
        pattern = f"%{_escaped_like(q.strip())}%"
        statement = statement.where(
            FDRRecord.internal_fdr_id.ilike(pattern, escape="\\")
            | FDRRecord.fdr_number.ilike(pattern, escape="\\")
            | FDRRecord.bank_name.ilike(pattern, escape="\\")
        )

    total = session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    sort_columns = {
        "internal_fdr_id": FDRRecord.internal_fdr_id,
        "bank_name": FDRRecord.bank_name,
        "fdr_number": FDRRecord.fdr_number,
        "amount": FDRRecord.amount,
        "issue_date": FDRRecord.issue_date,
        "maturity_date": FDRRecord.maturity_date,
        "record_status": FDRRecord.record_status,
        "updated_at": FDRRecord.updated_at,
    }
    column = sort_columns[sort_by]
    statement = statement.order_by(column.desc() if sort_order == "desc" else column.asc())
    records = session.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
    return FDRPage(items=[_response(item) for item in records], total=total, page=page, page_size=page_size)


@router.get("/{record_id}", response_model=FDRResponse)
def get_fdr(
    record_id: UUID,
    user: User = Depends(require_permission(Permission.FDR_READ)),
    session: Session = Depends(get_session),
) -> FDRResponse:
    return _response(_visible_record(session, user, record_id))


@router.post("", response_model=FDRResponse, status_code=status.HTTP_201_CREATED)
def create_fdr(
    body: FDRCreate,
    request: Request,
    user: User = Depends(require_permission(Permission.FDR_WRITE)),
    session: Session = Depends(get_session),
) -> FDRResponse:
    if user.institution_id is None:
        raise HTTPException(status_code=403, detail="An institution assignment is required")
    if body.institution_id is not None and body.institution_id != user.institution_id:
        raise HTTPException(status_code=403, detail="FDR records may only be created for the assigned institution")
    institution = session.get(Institution, user.institution_id)
    if institution is None:
        raise HTTPException(status_code=404, detail="Institution not found")
    record = FDRRecord(
        institution_id=user.institution_id,
        internal_fdr_id=f"FDR-{uuid4().hex.upper()}",
        bank_name=body.bank_name,
        branch_name=body.branch_name,
        fdr_number=body.fdr_number,
        amount=body.amount,
        currency=body.currency,
        issue_date=body.issue_date,
        maturity_date=body.maturity_date,
        record_status=FDRRecordStatus.DRAFT.value,
        verification_status=VerificationStatus.NOT_SUBMITTED.value,
        source_system="MANUAL_ENTRY",
        is_synthetic=True,
    )
    session.add(record)
    try:
        session.flush()
        write_audit_event(
            session, request, action="fdr_created", entity_type="fdr_record", entity_id=record.id,
            actor_id=user.id,
            change_summary={
                "fields": {
                    "internal_fdr_id": {"old": None, "new": record.internal_fdr_id},
                    "institution_id": {"old": None, "new": str(record.institution_id)},
                    "bank_name": {"old": None, "new": record.bank_name},
                    "branch_name": {"old": None, "new": record.branch_name},
                    "fdr_number": {"old": None, "new": record.fdr_number},
                    "amount": {"old": None, "new": str(record.amount)},
                    "currency": {"old": None, "new": record.currency},
                    "issue_date": {"old": None, "new": record.issue_date.isoformat()},
                    "maturity_date": {"old": None, "new": record.maturity_date.isoformat()},
                    "record_status": {"old": None, "new": record.record_status},
                    "verification_status": {"old": None, "new": record.verification_status},
                    "source_system": {"old": None, "new": record.source_system},
                    "is_synthetic": {"old": None, "new": record.is_synthetic},
                }
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return _response(record)


@router.patch("/{record_id}", response_model=FDRResponse)
def update_fdr(
    record_id: UUID,
    body: FDRPatch,
    request: Request,
    user: User = Depends(require_permission(Permission.FDR_WRITE)),
    session: Session = Depends(get_session),
) -> FDRResponse:
    statement = scope_fdr_query(select(FDRRecord), user).where(FDRRecord.id == record_id).with_for_update()
    record = session.scalar(statement)
    if record is None:
        raise HTTPException(status_code=404, detail="FDR record not found")
    if body.updated_at.tzinfo is None or body.updated_at.utcoffset() is None:
        raise HTTPException(status_code=422, detail="updated_at must include a timezone")
    if record.updated_at != body.updated_at:
        raise HTTPException(status_code=409, detail="FDR record changed since it was loaded; reload before saving")
    changes = body.model_dump(exclude_unset=True, exclude={"updated_at"})
    if not changes:
        raise HTTPException(status_code=422, detail="At least one editable field must be provided")
    new_issue = changes.get("issue_date", record.issue_date)
    new_maturity = changes.get("maturity_date", record.maturity_date)
    if new_maturity <= new_issue:
        raise HTTPException(status_code=422, detail="maturity_date must be after issue_date")
    if new_issue > date.today() + timedelta(days=1):
        raise HTTPException(status_code=422, detail="issue_date cannot be in the future")

    field_changes = {}
    for name in EDITABLE_FIELDS:
        if name not in changes:
            continue
        old_value = getattr(record, name)
        new_value = changes[name]
        if old_value != new_value:
            field_changes[name] = {"old": _json_value(old_value), "new": _json_value(new_value)}
            setattr(record, name, new_value)
    if not field_changes:
        raise HTTPException(status_code=422, detail="No FDR fields changed")
    try:
        session.flush()
        write_audit_event(
            session, request, action="fdr_updated", entity_type="fdr_record", entity_id=record.id,
            actor_id=user.id, change_summary={"fields": field_changes},
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return _response(record)


@router.post("/{record_id}/status", response_model=FDRResponse)
def change_fdr_status(
    record_id: UUID,
    body: FDRStatusChange,
    request: Request,
    user: User = Depends(require_permission(Permission.FDR_WRITE)),
    session: Session = Depends(get_session),
) -> FDRResponse:
    record = session.scalar(
        scope_fdr_query(select(FDRRecord), user).where(FDRRecord.id == record_id).with_for_update()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="FDR record not found")
    if body.record_status.value not in STATUS_TRANSITIONS.get(record.record_status, frozenset()):
        raise HTTPException(status_code=409, detail="FDR status transition is not allowed")
    previous = record.record_status
    record.record_status = body.record_status.value
    try:
        session.flush()
        write_audit_event(
            session, request, action="fdr_status_changed", entity_type="fdr_record", entity_id=record.id,
            actor_id=user.id,
            change_summary={
                "fields": {"record_status": {"old": previous, "new": record.record_status}},
                "remarks": body.remarks,
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return _response(record)


@router.get("/{record_id}/history", response_model=list[FDRHistoryItem])
def get_fdr_history(
    record_id: UUID,
    user: User = Depends(require_permission(Permission.FDR_READ)),
    session: Session = Depends(get_session),
) -> list[FDRHistoryItem]:
    _visible_record(session, user, record_id)
    rows = session.execute(
        select(AuditEvent, User.full_name)
        .outerjoin(User, User.id == AuditEvent.actor_id)
        .where(AuditEvent.entity_type == "fdr_record", AuditEvent.entity_id == record_id)
        .order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc())
    ).all()
    history = []
    for event, actor_name in rows:
        if event.action not in {"fdr_created", "fdr_updated", "fdr_status_changed"}:
            continue
        changed_fields = {
            field: change
            for field, change in event.change_summary.get("fields", {}).items()
            if field in HISTORY_FIELDS
            and isinstance(change, dict)
            and (event.action != "fdr_created" or change.get("new") not in (None, ""))
        }
        history.append(FDRHistoryItem(
            id=event.id,
            action=event.action,
            actor_name=actor_name or "System",
            timestamp=event.timestamp,
            changed_fields=changed_fields,
            remarks=event.change_summary.get("remarks"),
        ))
    return history
