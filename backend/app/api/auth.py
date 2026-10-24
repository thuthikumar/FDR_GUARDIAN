"""Login, refresh-token rotation, logout, and current-user API routes."""

import re
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import cookie_secure, refresh_token_expire_days, refresh_token_reuse_grace_seconds
from app.core.permissions import permissions_for_role
from app.core.security import create_access_token, create_refresh_token, hash_refresh_token, verify_password
from app.db.session import get_session
from app.models.auth import RefreshToken
from app.models.enums import UserRole
from app.models.users import User
from app.services.audit import write_audit_event


router = APIRouter(prefix="/auth", tags=["authentication"])
COOKIE_NAME = "fdr_refresh"
COOKIE_PATH = "/api/v1/auth"
GENERIC_LOGIN_ERROR = "Invalid email or password."
_SAFE_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=cookie_secure(),
        samesite="strict",
        path=COOKIE_PATH,
        max_age=refresh_token_expire_days() * 24 * 60 * 60,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        path=COOKIE_PATH,
        httponly=True,
        secure=cookie_secure(),
        samesite="strict",
    )


def _unauthorized_refresh() -> JSONResponse:
    response = JSONResponse(status_code=401, content={"detail": "Invalid or expired refresh token"})
    _clear_refresh_cookie(response)
    return response


def _audit_auth_failure(session: Session, request: Request, user: User | None, email: str) -> None:
    write_audit_event(
        session,
        request,
        action="login_failure",
        entity_type="authentication",
        entity_id=user.id if user else UUID(int=0),
        actor_id=user.id if user else None,
        change_summary={"email": email, "reason": "invalid_credentials"},
    )


@router.post("/login", response_model=AccessTokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> AccessTokenResponse:
    email = body.email.strip().lower()
    if not _SAFE_EMAIL.fullmatch(email):
        # Run the same Argon2 work before returning the common invalid-credentials response.
        verify_password(None, body.password)
        _audit_auth_failure(session, request, None, email[:254])
        session.commit()
        raise HTTPException(status_code=401, detail=GENERIC_LOGIN_ERROR)

    user = session.scalar(select(User).where(User.email == email).with_for_update())
    password_valid = verify_password(user.password_hash if user else None, body.password)
    now = datetime.now(timezone.utc)
    locked = bool(user and user.locked_until and user.locked_until > now)
    if user is None or not password_valid or not user.is_active or locked:
        if user is not None and not locked:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = now + timedelta(minutes=15)
                write_audit_event(
                    session,
                    request,
                    action="account_lockout",
                    entity_type="user",
                    entity_id=user.id,
                    actor_id=user.id,
                    change_summary={"locked_until": user.locked_until.isoformat()},
                )
        _audit_auth_failure(session, request, user, email)
        session.commit()
        raise HTTPException(status_code=401, detail=GENERIC_LOGIN_ERROR)

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    refresh_raw, refresh_hash = create_refresh_token()
    family_id = uuid4()
    session.add(RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        family_id=family_id,
        expires_at=now + timedelta(days=refresh_token_expire_days()),
    ))
    write_audit_event(
        session,
        request,
        action="login_success",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        change_summary={"email": user.email},
    )
    session.commit()
    _set_refresh_cookie(response, refresh_raw)
    return AccessTokenResponse(access_token=create_access_token(user.id))


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> AccessTokenResponse | JSONResponse:
    raw_token = request.cookies.get(COOKIE_NAME)
    if not raw_token:
        return _unauthorized_refresh()

    now = datetime.now(timezone.utc)
    stored = session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token)).with_for_update()
    )
    if stored is None:
        return _unauthorized_refresh()
    user = session.get(User, stored.user_id)
    if stored.expires_at <= now or user is None or not user.is_active:
        session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == stored.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        session.commit()
        return _unauthorized_refresh()

    if stored.revoked_at is not None:
        grace_seconds = refresh_token_reuse_grace_seconds()
        within_grace = (
            stored.replaced_by is not None
            and stored.revoked_at >= now - timedelta(seconds=grace_seconds)
        )
        replacement = session.get(RefreshToken, stored.replaced_by) if within_grace else None
        if replacement is not None and replacement.revoked_at is None and replacement.expires_at > now:
            # The replacement's raw value is intentionally not persisted. Returning no
            # Set-Cookie preserves whichever concurrent rotation response set the cookie.
            return AccessTokenResponse(access_token=create_access_token(user.id))
        session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == stored.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        write_audit_event(
            session,
            request,
            action="token_reuse_detected",
            entity_type="refresh_token_family",
            entity_id=stored.family_id,
            actor_id=stored.user_id,
            change_summary={"result": "family_revoked"},
        )
        session.commit()
        return _unauthorized_refresh()

    next_raw, next_hash = create_refresh_token()
    next_id = uuid4()
    next_row = RefreshToken(
        id=next_id,
        user_id=user.id,
        token_hash=next_hash,
        family_id=stored.family_id,
        expires_at=now + timedelta(days=refresh_token_expire_days()),
    )
    session.add(next_row)
    session.flush()
    stored.revoked_at = now
    stored.replaced_by = next_id
    session.commit()
    _set_refresh_cookie(response, next_raw)
    return AccessTokenResponse(access_token=create_access_token(user.id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> Response:
    raw_token = request.cookies.get(COOKIE_NAME)
    if raw_token:
        stored = session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token)).with_for_update()
        )
        if stored is not None and stored.revoked_at is None:
            stored.revoked_at = datetime.now(timezone.utc)
            write_audit_event(
                session,
                request,
                action="logout",
                entity_type="user",
                entity_id=stored.user_id,
                actor_id=stored.user_id,
                change_summary={"result": "refresh_token_revoked"},
            )
            session.commit()
    _clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict[str, object]:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "institution_id": str(user.institution_id) if user.institution_id else None,
        "permissions": sorted(permission.value for permission in permissions_for_role(user.role)),
    }
