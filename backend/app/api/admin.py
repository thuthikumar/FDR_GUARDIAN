"""Minimal user administration, protected by backend permissions."""

import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import require_permission
from app.core.permissions import Permission
from app.db.session import get_session
from app.models.enums import UserRole
from app.models.institutions import Institution
from app.models.users import User
from app.services.audit import write_audit_event


router = APIRouter(prefix="/admin/users", tags=["admin"], dependencies=[Depends(require_permission(Permission.USER_MANAGE))])
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    full_name: str = Field(min_length=1, max_length=160)
    role: UserRole
    institution_id: UUID | None = None
    is_active: bool = True


class UserPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: UserRole | None = None
    institution_id: UUID | None = None
    is_active: bool | None = None


def _user_response(user: User) -> dict[str, object]:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "institution_id": str(user.institution_id) if user.institution_id else None,
        "is_active": user.is_active,
        "is_synthetic": user.is_synthetic,
        "created_at": user.created_at,
    }


def _validate_role_institution(role: str, institution_id: UUID | None, session: Session) -> None:
    if role == UserRole.INSTITUTION_ADMIN.value and institution_id is None:
        raise HTTPException(status_code=422, detail="institution_id is required for institution_admin")
    if institution_id is not None and session.get(Institution, institution_id) is None:
        raise HTTPException(status_code=422, detail="Institution not found")


@router.get("")
def list_users(session: Session = Depends(get_session)) -> list[dict[str, object]]:
    users = session.scalars(select(User).order_by(User.email)).all()
    return [_user_response(user) for user in users]


@router.post("", status_code=201)
def create_user(
    body: UserCreate,
    request: Request,
    actor: User = Depends(require_permission(Permission.USER_MANAGE)),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    email = body.email.strip().lower()
    if not _EMAIL.fullmatch(email):
        raise HTTPException(status_code=422, detail="A valid email is required")
    if not body.full_name.strip():
        raise HTTPException(status_code=422, detail="full_name is required")
    _validate_role_institution(body.role.value, body.institution_id, session)
    user = User(
        email=email,
        full_name=body.full_name.strip(),
        role=body.role.value,
        institution_id=body.institution_id,
        is_active=body.is_active,
        is_synthetic=False,
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="A user with that email already exists") from None
    write_audit_event(
        session,
        request,
        action="user_created",
        entity_type="user",
        entity_id=user.id,
        actor_id=actor.id,
        change_summary={"email": user.email, "role": user.role, "institution_id": str(user.institution_id) if user.institution_id else None},
    )
    session.commit()
    session.refresh(user)
    return _user_response(user)


@router.patch("/{user_id}")
def patch_user(
    user_id: UUID,
    body: UserPatch,
    request: Request,
    actor: User = Depends(require_permission(Permission.USER_MANAGE)),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    before = {"role": user.role, "institution_id": user.institution_id, "is_active": user.is_active}
    changes = body.model_dump(exclude_unset=True)
    if changes.get("role", user.role) is None or changes.get("is_active", user.is_active) is None:
        raise HTTPException(status_code=422, detail="role and is_active cannot be null")
    role = changes.get("role", user.role)
    role = role.value if isinstance(role, UserRole) else role
    institution_id = changes.get("institution_id", user.institution_id)
    _validate_role_institution(role, institution_id, session)
    if "role" in changes:
        user.role = role
    if "institution_id" in changes:
        user.institution_id = institution_id
    if "is_active" in changes:
        user.is_active = changes["is_active"]
    if before["role"] != user.role:
        write_audit_event(
            session, request, action="role_changed", entity_type="user", entity_id=user.id, actor_id=actor.id,
            change_summary={"from_role": before["role"], "to_role": user.role},
        )
    if before["is_active"] and not user.is_active:
        write_audit_event(
            session, request, action="user_deactivated", entity_type="user", entity_id=user.id, actor_id=actor.id,
            change_summary={"is_active": False},
        )
    if before["institution_id"] != user.institution_id:
        write_audit_event(
            session, request, action="user_institution_changed", entity_type="user", entity_id=user.id, actor_id=actor.id,
            change_summary={"institution_id": str(user.institution_id) if user.institution_id else None},
        )
    session.commit()
    session.refresh(user)
    return _user_response(user)
