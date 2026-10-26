from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import AuditEvent, FDRRecord, Institution, User
from app.models.enums import FDRRecordStatus, InstitutionStatus, UserRole, VerificationStatus


def add_institution(session: Session, *, code: str | None = None, name: str = "Synthetic Registry Institution") -> Institution:
    institution = Institution(
        institution_code=code or f"REG-{uuid4().hex[:10]}",
        institution_name=name,
        status=InstitutionStatus.ACTIVE.value,
        is_synthetic=True,
    )
    session.add(institution)
    session.flush()
    return institution


def add_user(session: Session, role: str, institution_id=None) -> User:
    user = User(
        email=f"registry-{uuid4().hex}@synthetic.invalid",
        full_name="Synthetic Registry Tester",
        password_hash=hash_password("Synthetic-Registry-Passphrase!"),
        role=role,
        institution_id=institution_id,
        is_active=True,
        is_synthetic=True,
    )
    session.add(user)
    session.flush()
    return user


def add_fdr(session: Session, institution: Institution, **overrides) -> FDRRecord:
    values = {
        "institution_id": institution.id,
        "internal_fdr_id": f"REG-FDR-{uuid4().hex[:12]}",
        "bank_name": "Synthetic Registry Bank",
        "branch_name": None,
        "fdr_number": f"SYN-{uuid4().hex[:8]}",
        "amount": Decimal("1000.00"),
        "currency": "INR",
        "issue_date": date(2025, 1, 1),
        "maturity_date": date(2027, 1, 1),
        "record_status": FDRRecordStatus.ACTIVE.value,
        "verification_status": VerificationStatus.NOT_SUBMITTED.value,
        "source_system": "SYNTHETIC_TEST",
        "is_synthetic": True,
    }
    values.update(overrides)
    record = FDRRecord(**values)
    session.add(record)
    session.flush()
    return record


def auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def create_body(institution_id=None, **overrides):
    values = {
        "bank_name": "Synthetic New Bank",
        "branch_name": "Synthetic Central Branch",
        "fdr_number": "SYN-MANUAL-001",
        "amount": "25000.50",
        "currency": "INR",
        "issue_date": "2025-01-01",
        "maturity_date": "2027-01-01",
    }
    if institution_id is not None:
        values["institution_id"] = str(institution_id)
    values.update(overrides)
    return values


def test_institution_crud_scope_stats_and_audit(api_client, db_session: Session) -> None:
    system_admin = add_user(db_session, UserRole.SYSTEM_ADMIN.value)
    headers = auth(system_admin)
    created = api_client.post(
        "/api/v1/institutions",
        json={"institution_code": "REG-CREATE-001", "institution_name": "Synthetic Created Institution", "state": "Karnataka"},
        headers=headers,
    )
    assert created.status_code == 201
    assert created.json()["is_synthetic"] is True
    institution_id = created.json()["id"]
    assert "password_hash" not in created.text and "updated_by" not in created.text
    duplicate = api_client.post(
        "/api/v1/institutions",
        json={"institution_code": "REG-CREATE-001", "institution_name": "Duplicate Synthetic Institution"},
        headers=headers,
    )
    assert duplicate.status_code == 409

    institution = db_session.get(Institution, institution_id)
    assert institution is not None
    first = add_fdr(
        db_session, institution, amount=Decimal("125.25"), maturity_date=date.today() + timedelta(days=100)
    )
    add_fdr(db_session, institution, amount=Decimal("50.00"), record_status=FDRRecordStatus.MATURED.value)
    detail = api_client.get(f"/api/v1/institutions/{institution_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["stats"] == {
        "total_fdrs": 2,
        "active_fdrs": 1,
        "total_principal_amount": "175.25",
        "nearest_upcoming_maturity_date": (date.today() + timedelta(days=100)).isoformat(),
    }
    updated = api_client.patch(
        f"/api/v1/institutions/{institution_id}", json={"status": "inactive"}, headers=headers
    )
    assert updated.status_code == 200 and updated.json()["status"] == "inactive"
    events = db_session.scalars(
        select(AuditEvent).where(AuditEvent.entity_type == "institution", AuditEvent.entity_id == institution_id)
    ).all()
    assert {event.action for event in events} == {"institution_created", "institution_updated"}
    assert first.id


@pytest.mark.parametrize(
    "role,can_write_institution,can_write_fdr",
    [
        (UserRole.SYSTEM_ADMIN.value, True, False),
        (UserRole.INSTITUTION_ADMIN.value, False, True),
        (UserRole.VERIFICATION_OFFICER.value, False, False),
        (UserRole.ACCOUNTS_OFFICER.value, False, False),
        (UserRole.FINAL_APPROVER.value, False, False),
        (UserRole.READ_ONLY_AUDITOR.value, False, False),
    ],
)
def test_registry_permission_matrix(api_client, db_session: Session, role, can_write_institution, can_write_fdr) -> None:
    institution = add_institution(db_session)
    record = add_fdr(db_session, institution)
    user = add_user(db_session, role, institution.id if role == UserRole.INSTITUTION_ADMIN.value else None)
    headers = auth(user)
    assert api_client.get("/api/v1/institutions", headers=headers).status_code == 200
    assert api_client.get("/api/v1/fdrs", headers=headers).status_code == 200
    assert api_client.get(f"/api/v1/institutions/{institution.id}", headers=headers).status_code == 200
    assert api_client.get(f"/api/v1/fdrs/{record.id}", headers=headers).status_code == 200
    assert api_client.get(f"/api/v1/fdrs/{record.id}/history", headers=headers).status_code == 200
    institution_write = api_client.post(
        "/api/v1/institutions",
        json={"institution_code": f"REG-WRITE-{uuid4().hex[:8]}", "institution_name": "Synthetic Permission Test"},
        headers=headers,
    )
    assert institution_write.status_code == (201 if can_write_institution else 403)
    institution_patch = api_client.patch(
        f"/api/v1/institutions/{institution.id}", json={"status": "pending"}, headers=headers
    )
    assert institution_patch.status_code == (200 if can_write_institution else 403)
    fdr_write = api_client.post("/api/v1/fdrs", json=create_body(institution.id), headers=headers)
    assert fdr_write.status_code == (201 if can_write_fdr else 403)
    fdr_patch = api_client.patch(
        f"/api/v1/fdrs/{record.id}",
        json={"updated_at": record.updated_at.isoformat(), "bank_name": "Synthetic Permission Update"},
        headers=headers,
    )
    assert fdr_patch.status_code == (200 if can_write_fdr else 403)
    status_change = api_client.post(
        f"/api/v1/fdrs/{record.id}/status", json={"record_status": "matured", "remarks": "Synthetic permission check"}, headers=headers
    )
    assert status_change.status_code == (200 if can_write_fdr else 403)


@pytest.mark.parametrize(
    "body",
    [
        {"institution_code": "", "institution_name": "Synthetic"},
        {"institution_code": "X" * 33, "institution_name": "Synthetic"},
        {"institution_code": "REG-OK", "institution_name": " "},
        {"institution_code": "REG-OK", "institution_name": "I" * 201},
        {"institution_code": "REG-OK", "institution_name": "Synthetic", "institution_type": "T" * 81},
        {"institution_code": "REG-OK", "institution_name": "Synthetic", "state": "S" * 81},
        {"institution_code": "REG-OK", "institution_name": "Synthetic", "contact_email": "e" * 255},
        {"institution_code": "REG-OK", "institution_name": "Synthetic", "unknown_field": "rejected"},
    ],
)
def test_institution_create_validation(api_client, db_session: Session, body) -> None:
    admin = add_user(db_session, UserRole.SYSTEM_ADMIN.value)
    response = api_client.post("/api/v1/institutions", json=body, headers=auth(admin))
    assert response.status_code == 422


def test_institution_code_conflict_on_patch(api_client, db_session: Session) -> None:
    system_admin = add_user(db_session, UserRole.SYSTEM_ADMIN.value)
    first = add_institution(db_session, code="REG-PATCH-A")
    second = add_institution(db_session, code="REG-PATCH-B")
    response = api_client.patch(
        f"/api/v1/institutions/{second.id}", json={"institution_code": first.institution_code}, headers=auth(system_admin)
    )
    assert response.status_code == 409


def test_institution_admin_scope_and_cross_institution_fdr_endpoints(api_client, db_session: Session) -> None:
    own = add_institution(db_session, name="Synthetic Own Institution")
    other = add_institution(db_session, name="Synthetic Other Institution")
    own_fdr = add_fdr(db_session, own)
    other_fdr = add_fdr(db_session, other)
    admin = add_user(db_session, UserRole.INSTITUTION_ADMIN.value, own.id)
    headers = auth(admin)

    institutions = api_client.get("/api/v1/institutions", headers=headers)
    assert institutions.status_code == 200
    assert [row["id"] for row in institutions.json()["items"]] == [str(own.id)]
    assert api_client.get(f"/api/v1/institutions/{other.id}", headers=headers).status_code == 404
    fdr_list = api_client.get(f"/api/v1/fdrs?institution_id={other.id}", headers=headers)
    assert fdr_list.status_code == 200 and [row["id"] for row in fdr_list.json()["items"]] == [str(own_fdr.id)]
    for path in (
        f"/api/v1/fdrs/{other_fdr.id}",
        f"/api/v1/fdrs/{other_fdr.id}/history",
    ):
        assert api_client.get(path, headers=headers).status_code == 404
    assert api_client.patch(
        f"/api/v1/fdrs/{other_fdr.id}",
        json={"updated_at": other_fdr.updated_at.isoformat(), "bank_name": "Changed"},
        headers=headers,
    ).status_code == 404
    assert api_client.post(
        f"/api/v1/fdrs/{other_fdr.id}/status",
        json={"record_status": "cancelled", "remarks": "Synthetic scope test"},
        headers=headers,
    ).status_code == 404
    assert api_client.post("/api/v1/fdrs", json=create_body(other.id), headers=headers).status_code == 403


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": "0"},
        {"amount": "10.999"},
        {"currency": "inr"},
        {"maturity_date": "2024-12-31"},
        {"issue_date": (date.today() + timedelta(days=2)).isoformat(), "maturity_date": (date.today() + timedelta(days=30)).isoformat()},
        {"bank_name": "   "},
        {"fdr_number": "   "},
        {"bank_name": "x" * 161},
        {"fdr_number": "x" * 101},
        {"unknown_internal_field": "no"},
    ],
)
def test_fdr_create_validation(api_client, db_session: Session, overrides) -> None:
    institution = add_institution(db_session)
    admin = add_user(db_session, UserRole.INSTITUTION_ADMIN.value, institution.id)
    response = api_client.post("/api/v1/fdrs", json=create_body(institution.id, **overrides), headers=auth(admin))
    assert response.status_code == 422


def test_fdr_create_duplicates_allowed_and_response_hides_internal_model_fields(api_client, db_session: Session) -> None:
    institution = add_institution(db_session)
    admin = add_user(db_session, UserRole.INSTITUTION_ADMIN.value, institution.id)
    headers = auth(admin)
    one = api_client.post("/api/v1/fdrs", json=create_body(institution.id), headers=headers)
    two = api_client.post("/api/v1/fdrs", json=create_body(institution.id), headers=headers)
    assert one.status_code == two.status_code == 201
    assert one.json()["fdr_number"] == two.json()["fdr_number"]
    assert one.json()["source_system"] == "MANUAL_ENTRY"
    assert one.json()["verification_status"] == VerificationStatus.NOT_SUBMITTED.value
    assert one.json()["record_status"] == FDRRecordStatus.DRAFT.value
    assert one.json()["is_synthetic"] is True
    assert "external_record_id" not in one.json() and "source_updated_at" not in one.json()
    assert db_session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "fdr_created")) == 2


def test_fdr_history_creation_returns_business_fields_only(api_client, db_session: Session) -> None:
    institution = add_institution(db_session)
    admin = add_user(db_session, UserRole.INSTITUTION_ADMIN.value, institution.id)
    headers = auth(admin)
    created = api_client.post("/api/v1/fdrs", json=create_body(institution.id, branch_name=None), headers=headers)
    assert created.status_code == 201

    history = api_client.get(f"/api/v1/fdrs/{created.json()['id']}/history", headers=headers)
    assert history.status_code == 200
    changed_fields = history.json()[0]["changed_fields"]
    assert set(changed_fields) == {"bank_name", "fdr_number", "amount", "currency", "issue_date", "maturity_date", "record_status"}
    assert changed_fields["bank_name"]["new"] == "Synthetic New Bank"
    assert changed_fields["amount"]["new"] == "25000.50"
    assert not {"institution_id", "internal_fdr_id", "is_synthetic", "source_system", "verification_status", "id"} & set(changed_fields)


def test_fdr_update_stale_and_protected_fields(api_client, db_session: Session) -> None:
    institution = add_institution(db_session)
    admin = add_user(db_session, UserRole.INSTITUTION_ADMIN.value, institution.id)
    record = add_fdr(db_session, institution)
    record.updated_at = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.flush()
    headers = auth(admin)
    original_updated_at = record.updated_at.isoformat()
    patch = {"updated_at": original_updated_at, "bank_name": "Synthetic Updated Bank"}
    updated = api_client.patch(f"/api/v1/fdrs/{record.id}", json=patch, headers=headers)
    assert updated.status_code == 200 and updated.json()["bank_name"] == "Synthetic Updated Bank"
    stale = api_client.patch(f"/api/v1/fdrs/{record.id}", json=patch, headers=headers)
    assert stale.status_code == 409
    for protected in (
        {"verification_status": "verified"}, {"source_system": "HACKED"}, {"source_updated_at": "2026-01-01T00:00:00Z"},
        {"last_synced_at": "2026-01-01T00:00:00Z"}, {"is_synthetic": False}, {"institution_id": str(uuid4())},
        {"id": str(uuid4())}, {"internal_fdr_id": "CLIENT-CONTROLLED"}, {"record_status": "released"},
    ):
        response = api_client.patch(
            f"/api/v1/fdrs/{record.id}", json={"updated_at": updated.json()["updated_at"], **protected}, headers=headers
        )
        assert response.status_code == 422


@pytest.mark.parametrize(
    "changes",
    [
        {"amount": "0"},
        {"amount": "1.999"},
        {"currency": "usd"},
        {"bank_name": "x" * 161},
        {"branch_name": "x" * 161},
        {"fdr_number": " "},
        {"fdr_number": "x" * 101},
        {"issue_date": "2027-01-01"},
        {"maturity_date": "2024-12-31"},
        {"bank_name": None},
        {"updated_at": "2026-01-01T00:00:00"},
    ],
)
def test_fdr_patch_validation(api_client, db_session: Session, changes) -> None:
    institution = add_institution(db_session)
    admin = add_user(db_session, UserRole.INSTITUTION_ADMIN.value, institution.id)
    record = add_fdr(db_session, institution)
    body = {"updated_at": record.updated_at.isoformat(), "bank_name": "Synthetic Valid Patch", **changes}
    response = api_client.patch(f"/api/v1/fdrs/{record.id}", json=body, headers=auth(admin))
    assert response.status_code == 422


def test_fdr_status_transition_history_and_audit(api_client, db_session: Session) -> None:
    institution = add_institution(db_session)
    admin = add_user(db_session, UserRole.INSTITUTION_ADMIN.value, institution.id)
    record = add_fdr(db_session, institution, record_status=FDRRecordStatus.DRAFT.value)
    headers = auth(admin)
    active = api_client.post(
        f"/api/v1/fdrs/{record.id}/status", json={"record_status": "active", "remarks": "Synthetic activation"}, headers=headers
    )
    assert active.status_code == 200
    invalid = api_client.post(
        f"/api/v1/fdrs/{record.id}/status", json={"record_status": "released", "remarks": "Skip maturity"}, headers=headers
    )
    assert invalid.status_code == 409
    missing_remarks = api_client.post(
        f"/api/v1/fdrs/{record.id}/status", json={"record_status": "matured", "remarks": " "}, headers=headers
    )
    assert missing_remarks.status_code == 422
    history = api_client.get(f"/api/v1/fdrs/{record.id}/history", headers=headers)
    assert history.status_code == 200
    assert history.json()[0]["remarks"] == "Synthetic activation"
    assert history.json()[0]["changed_fields"]["record_status"] == {"old": "draft", "new": "active"}
    assert history.json()[0]["actor_name"] == admin.full_name
    audit_count = db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.entity_id == record.id)
    )
    assert audit_count == 1  # fixture insertion is not an API write; the status change is audited


@pytest.mark.parametrize(
    "previous,next_status",
    [
        ("draft", "active"),
        ("draft", "cancelled"),
        ("active", "matured"),
        ("active", "cancelled"),
        ("matured", "released"),
    ],
)
def test_allowed_fdr_status_transitions(api_client, db_session: Session, previous, next_status) -> None:
    institution = add_institution(db_session)
    admin = add_user(db_session, UserRole.INSTITUTION_ADMIN.value, institution.id)
    record = add_fdr(db_session, institution, record_status=previous)
    response = api_client.post(
        f"/api/v1/fdrs/{record.id}/status",
        json={"record_status": next_status, "remarks": "Synthetic transition matrix test"},
        headers=auth(admin),
    )
    assert response.status_code == 200
    assert response.json()["record_status"] == next_status


@pytest.mark.parametrize(
    "previous,next_status",
    [
        ("draft", "released"),
        ("active", "released"),
        ("matured", "active"),
        ("released", "active"),
        ("cancelled", "active"),
    ],
)
def test_invalid_fdr_status_transitions(api_client, db_session: Session, previous, next_status) -> None:
    institution = add_institution(db_session)
    admin = add_user(db_session, UserRole.INSTITUTION_ADMIN.value, institution.id)
    record = add_fdr(db_session, institution, record_status=previous)
    response = api_client.post(
        f"/api/v1/fdrs/{record.id}/status",
        json={"record_status": next_status, "remarks": "Synthetic invalid transition test"},
        headers=auth(admin),
    )
    assert response.status_code == 409


def test_fdr_history_reflects_business_field_edit(api_client, db_session: Session) -> None:
    institution = add_institution(db_session)
    admin = add_user(db_session, UserRole.INSTITUTION_ADMIN.value, institution.id)
    record = add_fdr(db_session, institution)
    response = api_client.patch(
        f"/api/v1/fdrs/{record.id}",
        json={"updated_at": record.updated_at.isoformat(), "amount": "2222.25"},
        headers=auth(admin),
    )
    assert response.status_code == 200
    history = api_client.get(f"/api/v1/fdrs/{record.id}/history", headers=auth(admin))
    assert history.json()[0]["changed_fields"]["amount"] == {"old": "1000.00", "new": "2222.25"}


def test_list_pagination_sort_and_like_wildcard_escaping(api_client, db_session: Session) -> None:
    institution = add_institution(db_session)
    add_fdr(db_session, institution, fdr_number="SYNTH-LITERAL-01")
    admin = add_user(db_session, UserRole.INSTITUTION_ADMIN.value, institution.id)
    headers = auth(admin)
    assert api_client.get("/api/v1/fdrs?page_size=101", headers=headers).status_code == 422
    assert api_client.get("/api/v1/fdrs?sort_by=source_system", headers=headers).status_code == 422
    assert api_client.get("/api/v1/fdrs?q=%25", headers=headers).json()["total"] == 0
    assert api_client.get("/api/v1/fdrs?q=_", headers=headers).json()["total"] == 0
    assert api_client.get("/api/v1/fdrs?q=SYNTH-LITERAL-01", headers=headers).json()["total"] == 1
    assert api_client.get("/api/v1/institutions?page_size=101", headers=headers).status_code == 422
    assert api_client.get("/api/v1/institutions?sort_by=password", headers=headers).status_code == 422


def test_writes_and_audit_event_roll_back_together(api_client, db_session: Session, monkeypatch) -> None:
    institution = add_institution(db_session)
    admin = add_user(db_session, UserRole.INSTITUTION_ADMIN.value, institution.id)

    def fail_audit(*args, **kwargs):
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr("app.api.fdrs.write_audit_event", fail_audit)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        api_client.post("/api/v1/fdrs", json=create_body(institution.id), headers=auth(admin))
    assert db_session.scalar(
        select(func.count()).select_from(FDRRecord).where(FDRRecord.fdr_number == "SYN-MANUAL-001")
    ) == 0
    assert db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "fdr_created")
    ) == 0


def test_registry_has_no_delete_routes(api_client) -> None:
    paths = app.openapi()["paths"]
    assert "delete" not in paths["/api/v1/institutions"]
    assert "delete" not in paths["/api/v1/institutions/{institution_id}"]
    assert "delete" not in paths["/api/v1/fdrs"]
    assert "delete" not in paths["/api/v1/fdrs/{record_id}"]
