"""Institution registry endpoints with backend-enforced role scoping."""

from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.permissions import Permission
from app.db.session import get_session
from app.models.enums import FDRRecordStatus, InstitutionStatus, UserRole
from app.models.fdr import FDRRecord
from app.models.institutions import Institution
from app.models.users import User
from app.schemas.institutions import (
    InstitutionCreate,
    InstitutionDetailResponse,
    InstitutionPage,
    InstitutionPatch,
    InstitutionResponse,
    InstitutionStats,
)
from app.services.audit import write_audit_event


router = APIRouter(prefix="/institutions", tags=["institutions"])


def _institution_response(institution: Institution) -> InstitutionResponse:
    return InstitutionResponse(
        id=institution.id,
        institution_code=institution.institution_code,
        institution_name=institution.institution_name,
        institution_type=institution.institution_type,
        state=institution.state,
        contact_email=institution.contact_email,
        status=institution.status,
        is_synthetic=institution.is_synthetic,
        created_at=institution.created_at,
        updated_at=institution.updated_at,
    )


def _scope_institutions(statement, user: User):
    if user.role == UserRole.INSTITUTION_ADMIN.value:
        if user.institution_id is None:
            raise HTTPException(status_code=404, detail="Institution not found")
        statement = statement.where(Institution.id == user.institution_id)
    return statement


def _get_accessible_institution(session: Session, user: User, institution_id: UUID) -> Institution:
    institution = session.scalar(
        _scope_institutions(select(Institution), user).where(Institution.id == institution_id)
    )
    if institution is None:
        raise HTTPException(status_code=404, detail="Institution not found")
    return institution


@router.get("", response_model=InstitutionPage)
def list_institutions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    q: str | None = Query(default=None, max_length=200),
    institution_status: InstitutionStatus | None = Query(default=None, alias="status"),
    state: str | None = Query(default=None, max_length=80),
    sort_by: Literal["institution_name", "institution_code", "state", "status", "created_at"] = "institution_name",
    sort_order: Literal["asc", "desc"] = "asc",
    user: User = Depends(require_permission(Permission.INSTITUTION_READ)),
    session: Session = Depends(get_session),
) -> InstitutionPage:
    statement = _scope_institutions(select(Institution), user)
    if q:
        term = q.strip()
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        statement = statement.where(
            Institution.institution_name.ilike(pattern, escape="\\")
            | Institution.institution_code.ilike(pattern, escape="\\")
        )
    if institution_status:
        statement = statement.where(Institution.status == institution_status)
    if state:
        statement = statement.where(Institution.state.ilike(f"%{state.strip()}%"))

    total = session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    sort_columns = {
        "institution_name": Institution.institution_name,
        "institution_code": Institution.institution_code,
        "state": Institution.state,
        "status": Institution.status,
        "created_at": Institution.created_at,
    }
    sort_column = sort_columns[sort_by]
    statement = statement.order_by(sort_column.desc() if sort_order == "desc" else sort_column.asc())
    rows = session.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
    return InstitutionPage(
        items=[_institution_response(item) for item in rows], total=total, page=page, page_size=page_size
    )


@router.get("/{institution_id}", response_model=InstitutionDetailResponse)
def get_institution(
    institution_id: UUID,
    user: User = Depends(require_permission(Permission.INSTITUTION_READ)),
    session: Session = Depends(get_session),
) -> InstitutionDetailResponse:
    institution = _get_accessible_institution(session, user, institution_id)
    today = date.today()
    stats = session.execute(
        select(
            func.count(FDRRecord.id),
            func.count(case((FDRRecord.record_status == FDRRecordStatus.ACTIVE.value, 1))),
            func.coalesce(func.sum(FDRRecord.amount), 0),
            func.min(
                case(
                    (
                        and_(
                            FDRRecord.maturity_date >= today,
                            FDRRecord.record_status.in_([FDRRecordStatus.DRAFT.value, FDRRecordStatus.ACTIVE.value]),
                        ),
                        FDRRecord.maturity_date,
                    ),
                    else_=None,
                )
            ),
        ).where(FDRRecord.institution_id == institution.id)
    ).one()
    return InstitutionDetailResponse(
        **_institution_response(institution).model_dump(),
        stats=InstitutionStats(
            total_fdrs=stats[0],
            active_fdrs=stats[1],
            total_principal_amount=str(stats[2]),
            nearest_upcoming_maturity_date=stats[3].isoformat() if stats[3] else None,
        ),
    )


@router.post("", response_model=InstitutionResponse, status_code=status.HTTP_201_CREATED)
def create_institution(
    body: InstitutionCreate,
    request: Request,
    user: User = Depends(require_permission(Permission.INSTITUTION_WRITE)),
    session: Session = Depends(get_session),
) -> InstitutionResponse:
    if session.scalar(select(Institution.id).where(Institution.institution_code == body.institution_code)):
        raise HTTPException(status_code=409, detail="Institution code already exists")
    institution = Institution(**body.model_dump(), is_synthetic=True)
    session.add(institution)
    try:
        session.flush()
        write_audit_event(
            session, request,
            action="institution_created", entity_type="institution", entity_id=institution.id,
            actor_id=user.id,
            change_summary={"fields": {
                name: {"old": None, "new": value.value if hasattr(value, "value") else value}
                for name, value in {
                    "institution_code": institution.institution_code,
                    "institution_name": institution.institution_name,
                    "institution_type": institution.institution_type,
                    "state": institution.state,
                    "contact_email": institution.contact_email,
                    "status": institution.status,
                }.items()
            }},
        )
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Institution code already exists") from None
    except Exception:
        session.rollback()
        raise
    return _institution_response(institution)


@router.patch("/{institution_id}", response_model=InstitutionResponse)
def update_institution(
    institution_id: UUID,
    body: InstitutionPatch,
    request: Request,
    user: User = Depends(require_permission(Permission.INSTITUTION_WRITE)),
    session: Session = Depends(get_session),
) -> InstitutionResponse:
    institution = session.scalar(select(Institution).where(Institution.id == institution_id).with_for_update())
    if institution is None:
        raise HTTPException(status_code=404, detail="Institution not found")
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="At least one field must be provided")
    if "institution_code" in changes:
        duplicate = session.scalar(
            select(Institution.id).where(
                Institution.institution_code == changes["institution_code"], Institution.id != institution.id
            )
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Institution code already exists")
    audit_fields = {}
    for name, value in changes.items():
        old_value = getattr(institution, name)
        if old_value != value:
            audit_fields[name] = {"old": old_value.value if hasattr(old_value, "value") else old_value, "new": value.value if hasattr(value, "value") else value}
            setattr(institution, name, value)
    if not audit_fields:
        raise HTTPException(status_code=422, detail="No institution fields changed")
    session.add(institution)
    try:
        write_audit_event(
            session, request,
            action="institution_updated", entity_type="institution", entity_id=institution.id,
            actor_id=user.id, change_summary={"fields": audit_fields},
        )
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Institution code already exists") from None
    except Exception:
        session.rollback()
        raise
    return _institution_response(institution)
