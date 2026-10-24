"""Backend institution scoping helpers for record queries and direct access."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import Select, select

from app.models.enums import UserRole
from app.models.fdr import FDRRecord
from app.models.users import User


def scope_fdr_query(statement: Select, user: User) -> Select:
    """Scope institution admins to their own institution; all other roles are global."""
    if user.role == UserRole.INSTITUTION_ADMIN.value:
        if user.institution_id is None:
            raise HTTPException(status_code=404, detail="Record not found")
        statement = statement.where(FDRRecord.institution_id == user.institution_id)
    return statement


def get_accessible_fdr(session, user: User, record_id: UUID) -> FDRRecord:
    statement = scope_fdr_query(select(FDRRecord), user).where(FDRRecord.id == record_id)
    record = session.scalar(statement)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


def ensure_institution_access(user: User, institution_id: UUID) -> None:
    """Hide cross-institution record existence from institution administrators."""
    if user.role == UserRole.INSTITUTION_ADMIN.value and user.institution_id != institution_id:
        raise HTTPException(status_code=404, detail="Record not found")
