from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.permissions import Permission, permissions_for_role
from app.core.config import refresh_token_reuse_grace_seconds
from app.core.security import create_access_token, hash_password, hash_refresh_token, verify_password
from app.db.session import get_session
from app.main import app
from app.models import AuditEvent, FDRRecord, Institution, RefreshToken, User
from app.models.enums import FDRRecordStatus, InstitutionStatus, UserRole, VerificationStatus
from app.services.institution_access import get_accessible_fdr


TEST_PASSWORD = "Synthetic-Phase3-Passphrase!"
GENERIC_ERROR = "Invalid email or password."


def add_institution(session: Session, name: str) -> Institution:
    institution = Institution(
        institution_code=f"TST-{uuid4().hex[:8]}",
        institution_name=name,
        status=InstitutionStatus.ACTIVE.value,
        is_synthetic=True,
    )
    session.add(institution)
    session.flush()
    return institution


def add_user(
    session: Session,
    *,
    role: str = UserRole.SYSTEM_ADMIN.value,
    password: str | None = TEST_PASSWORD,
    active: bool = True,
    institution_id=None,
    synthetic: bool = True,
) -> User:
    user = User(
        email=f"phase3-{uuid4().hex}@synthetic.invalid",
        full_name="Synthetic Phase Three User",
        password_hash=hash_password(password) if password else None,
        role=role,
        institution_id=institution_id,
        is_active=active,
        is_synthetic=synthetic,
    )
    session.add(user)
    session.flush()
    return user


def add_fdr(session: Session, institution: Institution) -> FDRRecord:
    record = FDRRecord(
        institution_id=institution.id,
        internal_fdr_id=f"TST-FDR-{uuid4().hex[:10]}",
        bank_name="Synthetic Test Bank",
        fdr_number=f"SYNTH-{uuid4().hex[:8]}",
        amount="10000.00",
        issue_date=date(2025, 1, 1),
        maturity_date=date(2026, 1, 1),
        record_status=FDRRecordStatus.ACTIVE.value,
        verification_status=VerificationStatus.SUBMITTED.value,
        source_system="SYNTHETIC_TEST",
        is_synthetic=True,
    )
    session.add(record)
    session.flush()
    return record


_test_router = APIRouter(prefix="/__test")


@_test_router.get("/fdr/{record_id}")
def only_read_fdr_endpoint(
    record_id: UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    record = get_accessible_fdr(session, user, record_id)
    return {"id": str(record.id), "institution_id": str(record.institution_id)}


app.include_router(_test_router)


def test_password_hash_is_argon2id_and_not_reversible() -> None:
    hashed = hash_password(TEST_PASSWORD)
    assert hashed.startswith("$argon2id$")
    assert hashed != TEST_PASSWORD
    assert verify_password(hashed, TEST_PASSWORD)
    assert not verify_password(hashed, "wrong-password")


def test_login_success_sets_hardened_cookie_and_me_hides_secrets(api_client, db_session: Session) -> None:
    institution = add_institution(db_session, "Synthetic Login Institution")
    user = add_user(db_session, role=UserRole.INSTITUTION_ADMIN.value, institution_id=institution.id)
    response = api_client.post("/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD}, headers={"X-Request-ID": "login-success-001"})

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert "path=/api/v1/auth" in cookie
    assert "secure" not in cookie
    me = api_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"})
    assert me.status_code == 200
    assert me.json()["full_name"] == user.full_name
    assert me.json()["role"] == UserRole.INSTITUTION_ADMIN.value
    assert "password_hash" not in me.text and "refresh_token" not in me.text
    event = db_session.scalar(select(AuditEvent).where(AuditEvent.action == "login_success"))
    assert event is not None and event.correlation_id == "login-success-001"
    refresh_raw = api_client.cookies.get("fdr_refresh")
    stored_refresh = db_session.scalar(select(RefreshToken).where(RefreshToken.user_id == user.id))
    assert refresh_raw and stored_refresh is not None
    assert stored_refresh.token_hash == hash_refresh_token(refresh_raw) and refresh_raw != stored_refresh.token_hash
    assert response.json()["access_token"] not in str(event.change_summary)
    assert refresh_raw not in str(event.change_summary) and TEST_PASSWORD not in str(event.change_summary)


def test_unknown_wrong_and_inactive_login_errors_are_indistinguishable(api_client, db_session: Session) -> None:
    wrong_user = add_user(db_session)
    inactive_user = add_user(db_session, active=False)
    responses = [
        api_client.post("/api/v1/auth/login", json={"email": wrong_user.email, "password": "incorrect-password"}),
        api_client.post("/api/v1/auth/login", json={"email": "missing@synthetic.invalid", "password": TEST_PASSWORD}),
        api_client.post("/api/v1/auth/login", json={"email": inactive_user.email, "password": TEST_PASSWORD}),
    ]
    assert {(response.status_code, response.json()["detail"]) for response in responses} == {(401, GENERIC_ERROR)}
    events = db_session.scalars(select(AuditEvent).where(AuditEvent.action == "login_failure")).all()
    assert len(events) == 3
    assert all("password" not in event.change_summary and "incorrect-password" not in str(event.change_summary) for event in events)
    assert all("password_hash" not in response.text for response in responses)


def test_lockout_after_five_failures_and_success_resets_counter(api_client, db_session: Session) -> None:
    user = add_user(db_session)
    for _ in range(5):
        response = api_client.post("/api/v1/auth/login", json={"email": user.email, "password": "wrong-password"})
        assert response.status_code == 401 and response.json()["detail"] == GENERIC_ERROR
    db_session.refresh(user)
    assert user.failed_login_attempts == 5
    assert user.locked_until is not None and user.locked_until > datetime.now(timezone.utc)
    assert db_session.scalar(select(AuditEvent).where(AuditEvent.action == "account_lockout")) is not None

    user.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    response = api_client.post("/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert response.status_code == 200
    db_session.refresh(user)
    assert user.failed_login_attempts == 0 and user.locked_until is None and user.last_login_at is not None


def test_refresh_rotation_grace_then_reuse_revokes_family(api_client, db_session: Session) -> None:
    user = add_user(db_session)
    login = api_client.post("/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert login.status_code == 200
    first_raw = api_client.cookies.get("fdr_refresh")
    assert first_raw
    first_hash = hash_refresh_token(first_raw)

    rotated = api_client.post("/api/v1/auth/refresh")
    assert rotated.status_code == 200
    second_raw = api_client.cookies.get("fdr_refresh")
    assert second_raw and second_raw != first_raw
    first_row = db_session.scalar(select(RefreshToken).where(RefreshToken.token_hash == first_hash))
    assert first_row is not None and first_row.revoked_at is not None and first_row.replaced_by is not None

    api_client.cookies.set("fdr_refresh", first_raw, path="/api/v1/auth")
    concurrent = api_client.post("/api/v1/auth/refresh")
    assert concurrent.status_code == 200
    assert "set-cookie" not in concurrent.headers

    first_row.revoked_at = datetime.now(timezone.utc) - timedelta(
        seconds=refresh_token_reuse_grace_seconds() + 1
    )
    db_session.flush()
    reused = api_client.post("/api/v1/auth/refresh")
    assert reused.status_code == 401
    family = db_session.scalars(select(RefreshToken).where(RefreshToken.family_id == first_row.family_id)).all()
    assert family and all(token.revoked_at is not None for token in family)
    assert db_session.scalar(select(AuditEvent).where(AuditEvent.action == "token_reuse_detected")) is not None


def test_refresh_rejects_missing_tampered_and_expired_tokens(api_client, db_session: Session) -> None:
    assert api_client.post("/api/v1/auth/refresh").status_code == 401
    api_client.cookies.set("fdr_refresh", "not-a-real-refresh-token", path="/api/v1/auth")
    assert api_client.post("/api/v1/auth/refresh").status_code == 401

    user = add_user(db_session)
    api_client.cookies.clear()
    api_client.post("/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    raw = api_client.cookies.get("fdr_refresh")
    row = db_session.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw)))
    assert row is not None
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.flush()
    response = api_client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
    assert row.revoked_at is not None


def test_logout_revokes_refresh_and_clears_cookie(api_client, db_session: Session) -> None:
    user = add_user(db_session)
    api_client.post("/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    raw = api_client.cookies.get("fdr_refresh")
    row = db_session.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw)))
    response = api_client.post("/api/v1/auth/logout")
    assert response.status_code == 204
    assert "max-age=0" in response.headers["set-cookie"].lower()
    db_session.refresh(row)
    assert row.revoked_at is not None
    assert db_session.scalar(select(AuditEvent).where(AuditEvent.action == "logout")) is not None
    api_client.cookies.set("fdr_refresh", raw, path="/api/v1/auth")
    assert api_client.post("/api/v1/auth/refresh").status_code == 401


@pytest.mark.parametrize("authorization", [None, "Bearer malformed", "Bearer expired"])
def test_me_rejects_missing_tampered_and_expired_access_tokens(api_client, authorization) -> None:
    headers = {"Authorization": authorization} if authorization else {}
    if authorization == "Bearer expired":
        user_id = uuid4()
        from app.core.config import jwt_secret_key

        token = jwt.encode({"sub": str(user_id), "typ": "access", "exp": datetime.now(timezone.utc) - timedelta(seconds=2)}, jwt_secret_key(), algorithm="HS256")
        headers["Authorization"] = f"Bearer {token}"
    response = api_client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401


_expected_matrix = {
    "system_admin": {"user.manage", "audit.read", "institution.read", "institution.write", "fdr.read", "alert.read", "case.read", "report.read", "integration.manage"},
    "institution_admin": {"institution.read", "fdr.read", "fdr.write", "document.upload", "document.read", "case.read", "alert.read", "report.read"},
    "verification_officer": {"institution.read", "fdr.read", "document.read", "extraction.review", "case.read", "case.review", "alert.read", "alert.manage", "report.read"},
    "accounts_officer": {"institution.read", "fdr.read", "case.read", "case.financial_review", "release.record", "alert.read", "report.read", "report.export"},
    "final_approver": {"institution.read", "fdr.read", "document.read", "case.read", "case.approve", "alert.read", "report.read"},
    "read_only_auditor": {"institution.read", "fdr.read", "document.read", "case.read", "alert.read", "audit.read", "report.read", "report.export"},
}


@pytest.mark.parametrize("role,expected", _expected_matrix.items())
def test_permissions_match_proposed_matrix(role, expected) -> None:
    assert {permission.value for permission in permissions_for_role(role)} == expected


def test_read_only_auditor_has_no_write_permissions() -> None:
    auditor_permissions = permissions_for_role(UserRole.READ_ONLY_AUDITOR.value)
    assert not auditor_permissions & {
        Permission.USER_MANAGE, Permission.FDR_WRITE, Permission.DOCUMENT_UPLOAD, Permission.EXTRACTION_REVIEW,
        Permission.CASE_REVIEW, Permission.CASE_FINANCIAL_REVIEW, Permission.CASE_APPROVE,
        Permission.RELEASE_RECORD, Permission.ALERT_MANAGE, Permission.INTEGRATION_MANAGE, Permission.INSTITUTION_WRITE,
    }


def test_authenticated_role_without_user_manage_gets_403(api_client, db_session: Session) -> None:
    user = add_user(db_session, role=UserRole.VERIFICATION_OFFICER.value)
    token = create_access_token(user.id)
    response = api_client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_cors_allows_credentials_for_only_configured_frontend_origin(api_client) -> None:
    allowed = api_client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"
    assert allowed.headers.get("access-control-allow-credentials") == "true"
    denied = api_client.options(
        "/api/v1/auth/login",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in denied.headers


def test_institution_admin_isolation_returns_404_for_other_institution(api_client, db_session: Session) -> None:
    institution_a = add_institution(db_session, "Synthetic Institution A")
    institution_b = add_institution(db_session, "Synthetic Institution B")
    fdr_a = add_fdr(db_session, institution_a)
    fdr_b = add_fdr(db_session, institution_b)
    institution_admin = add_user(db_session, role=UserRole.INSTITUTION_ADMIN.value, institution_id=institution_a.id)
    response = api_client.get(f"/__test/fdr/{fdr_a.id}", headers={"Authorization": f"Bearer {create_access_token(institution_admin.id)}"})
    assert response.status_code == 200
    hidden = api_client.get(f"/__test/fdr/{fdr_b.id}", headers={"Authorization": f"Bearer {create_access_token(institution_admin.id)}"})
    assert hidden.status_code == 404 and hidden.json()["detail"] == "Record not found"

    global_user = add_user(db_session, role=UserRole.VERIFICATION_OFFICER.value)
    global_response = api_client.get(f"/__test/fdr/{fdr_b.id}", headers={"Authorization": f"Bearer {create_access_token(global_user.id)}"})
    assert global_response.status_code == 200


def test_admin_create_role_change_deactivate_and_audit(api_client, db_session: Session) -> None:
    institution = add_institution(db_session, "Synthetic Admin Target")
    admin = add_user(db_session, role=UserRole.SYSTEM_ADMIN.value)
    headers = {"Authorization": f"Bearer {create_access_token(admin.id)}", "X-Request-ID": "admin-operation-42"}
    created = api_client.post(
        "/api/v1/admin/users",
        json={"email": "new-officer@synthetic.invalid", "full_name": "New Synthetic Officer", "role": "verification_officer"},
        headers=headers,
    )
    assert created.status_code == 201
    created_body = created.json()
    assert "password_hash" not in created.text
    target_id = created_body["id"]
    promoted = api_client.patch(
        f"/api/v1/admin/users/{target_id}",
        json={"role": "institution_admin", "institution_id": str(institution.id)},
        headers=headers,
    )
    assert promoted.status_code == 200 and promoted.json()["institution_id"] == str(institution.id)
    deactivated = api_client.patch(f"/api/v1/admin/users/{target_id}", json={"is_active": False}, headers=headers)
    assert deactivated.status_code == 200 and deactivated.json()["is_active"] is False
    target_uuid = UUID(target_id)
    actions = set(db_session.scalars(select(AuditEvent.action).where(AuditEvent.entity_id == target_uuid)).all())
    assert {"user_created", "role_changed", "user_deactivated", "user_institution_changed"} <= actions
    events = db_session.scalars(select(AuditEvent).where(AuditEvent.entity_id == target_uuid)).all()
    assert all(event.correlation_id == "admin-operation-42" for event in events)
    listed = api_client.get("/api/v1/admin/users", headers=headers)
    assert listed.status_code == 200 and "password_hash" not in listed.text


def test_dev_password_command_refuses_production_and_missing_password(api_client, db_session: Session, monkeypatch) -> None:
    from app.db.set_dev_passwords import main, run_set_dev_passwords
    from app.core.config import jwt_secret_key

    with pytest.raises(RuntimeError, match="production"):
        run_set_dev_passwords(db_session, TEST_PASSWORD, "production")
    with pytest.raises(RuntimeError, match="must be set"):
        run_set_dev_passwords(db_session, None, "development")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SEED_DEV_PASSWORD", TEST_PASSWORD)
    with pytest.raises(SystemExit, match="disabled"):
        main()
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("SEED_DEV_PASSWORD", raising=False)
    monkeypatch.setattr("app.db.set_dev_passwords.make_engine", lambda *_: pytest.fail("opened DB without dev password"))
    with pytest.raises(SystemExit, match="SEED_DEV_PASSWORD"):
        main()

    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="required"):
        jwt_secret_key()
    monkeypatch.setenv("JWT_SECRET_KEY", "too-short")
    with pytest.raises(RuntimeError, match="32 characters"):
        jwt_secret_key()


def test_production_cookie_setting_must_be_secure(monkeypatch) -> None:
    from app.core.config import cookie_secure

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    with pytest.raises(RuntimeError, match="must be true"):
        cookie_secure()
    monkeypatch.setenv("COOKIE_SECURE", "true")
    assert cookie_secure() is True


def test_jwt_secret_rejects_long_placeholder(monkeypatch) -> None:
    from app.core.config import jwt_secret_key

    monkeypatch.setenv("JWT_SECRET_KEY", "replace-with-a-placeholder-value-that-is-long-enough")
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        jwt_secret_key()


def test_dev_password_command_updates_synthetic_users_only(db_session: Session) -> None:
    from app.db.set_dev_passwords import run_set_dev_passwords

    synthetic = add_user(db_session, synthetic=True, password=None)
    regular = add_user(db_session, synthetic=False, password=None)
    count = run_set_dev_passwords(db_session, TEST_PASSWORD, "development")
    assert count == 1
    db_session.refresh(synthetic)
    db_session.refresh(regular)
    assert synthetic.password_hash and verify_password(synthetic.password_hash, TEST_PASSWORD)
    assert synthetic.password_changed_at is not None
    assert regular.password_hash is None
