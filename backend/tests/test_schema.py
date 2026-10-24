from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Alert,
    AuditEvent,
    FDRRecord,
    Institution,
    User,
    VerificationCase,
)
from app.models.enums import AlertSeverity, AlertStatus, FDRRecordStatus, InstitutionStatus, UserRole, VerificationStatus
from conftest import EXPECTED_TABLES


def add_institution(session: Session) -> Institution:
    institution = Institution(
        institution_code=f"TST-{uuid4().hex[:8]}",
        institution_name="Synthetic Test Institution",
        status=InstitutionStatus.ACTIVE.value,
        is_synthetic=True,
    )
    session.add(institution)
    session.flush()
    return institution


def add_user(session: Session, institution: Institution, role: str = UserRole.SYSTEM_ADMIN.value) -> User:
    user = User(
        email=f"{uuid4().hex}@synthetic.invalid",
        full_name="Synthetic Test User",
        role=role,
        institution_id=institution.id,
        is_synthetic=True,
    )
    session.add(user)
    session.flush()
    return user


def add_fdr(
    session: Session,
    institution: Institution,
    *,
    internal_id: str | None = None,
    fdr_number: str = "SYNTH-FDR-TEST-DUPLICATE",
    amount: Decimal = Decimal("1000.00"),
    issue_date: date = date(2025, 1, 1),
    maturity_date: date = date(2026, 1, 1),
    verification_status: str = VerificationStatus.SUBMITTED.value,
) -> FDRRecord:
    record = FDRRecord(
        institution_id=institution.id,
        internal_fdr_id=internal_id or f"TST-FDR-{uuid4().hex[:10]}",
        bank_name="Synthetic Test Bank",
        fdr_number=fdr_number,
        amount=amount,
        issue_date=issue_date,
        maturity_date=maturity_date,
        record_status=FDRRecordStatus.ACTIVE.value,
        verification_status=verification_status,
        source_system="SYNTHETIC_TEST",
        is_synthetic=True,
    )
    session.add(record)
    session.flush()
    return record


def test_all_expected_tables_exist(db_engine) -> None:
    assert EXPECTED_TABLES <= set(inspect(db_engine).get_table_names())


def test_amount_and_maturity_checks_reject_invalid_records(db_session: Session) -> None:
    institution = add_institution(db_session)
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            add_fdr(db_session, institution, amount=Decimal("0.00"), internal_id="TST-FDR-BAD-AMOUNT")

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            add_fdr(
                db_session,
                institution,
                issue_date=date(2026, 2, 1),
                maturity_date=date(2026, 1, 1),
                internal_id="TST-FDR-BAD-DATES",
            )


def test_invalid_role_and_workflow_status_are_rejected(db_session: Session) -> None:
    institution = add_institution(db_session)
    invalid_user = User(
        email=f"invalid-{uuid4().hex}@synthetic.invalid",
        full_name="Invalid Synthetic Role",
        role="not_a_real_role",
        institution_id=institution.id,
        is_synthetic=True,
    )
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(invalid_user)
            db_session.flush()

    record = add_fdr(db_session, institution)
    invalid_case = VerificationCase(
        fdr_record_id=record.id,
        status="not_a_workflow_state",
        reason="Synthetic constraint test.",
    )
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(invalid_case)
            db_session.flush()


def test_fdr_number_is_not_unique_but_internal_id_is(db_session: Session) -> None:
    institution = add_institution(db_session)
    add_fdr(db_session, institution, internal_id="TST-FDR-UNIQUE-0001", fdr_number="SYNTH-SHARED-NUMBER")
    add_fdr(db_session, institution, internal_id="TST-FDR-UNIQUE-0002", fdr_number="SYNTH-SHARED-NUMBER")

    duplicate_internal_id = FDRRecord(
        institution_id=institution.id,
        internal_fdr_id="TST-FDR-UNIQUE-0001",
        bank_name="Synthetic Test Bank",
        fdr_number="SYNTH-OTHER-NUMBER",
        amount=Decimal("2000.00"),
        issue_date=date(2025, 1, 1),
        maturity_date=date(2026, 1, 1),
        record_status=FDRRecordStatus.ACTIVE.value,
        verification_status=VerificationStatus.SUBMITTED.value,
        source_system="SYNTHETIC_TEST",
        is_synthetic=True,
    )
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(duplicate_internal_id)
            db_session.flush()


def test_active_alert_uniqueness_releases_after_resolution(db_session: Session) -> None:
    institution = add_institution(db_session)
    record = add_fdr(db_session, institution)
    first = Alert(
        fdr_record_id=record.id,
        alert_type="synthetic_test_duplicate",
        severity=AlertSeverity.HIGH.value,
        explanation="Synthetic alert constraint test.",
        status=AlertStatus.OPEN.value,
    )
    db_session.add(first)
    db_session.flush()
    second = Alert(
        fdr_record_id=record.id,
        alert_type="synthetic_test_duplicate",
        severity=AlertSeverity.HIGH.value,
        explanation="Second synthetic alert.",
        status=AlertStatus.ACKNOWLEDGED.value,
    )
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(second)
            db_session.flush()

    first.status = AlertStatus.RESOLVED.value
    first.resolved_at = datetime.now(timezone.utc)
    db_session.flush()
    db_session.add(second)
    db_session.flush()


def test_audit_events_reject_update_and_delete(db_session: Session) -> None:
    institution = add_institution(db_session)
    actor = add_user(db_session, institution)
    event = AuditEvent(
        actor_id=actor.id,
        action="synthetic_test",
        entity_type="institution",
        entity_id=institution.id,
        change_summary={"synthetic": True},
    )
    db_session.add(event)
    db_session.flush()

    with pytest.raises(DBAPIError):
        with db_session.begin_nested():
            db_session.execute(text("UPDATE audit_events SET action = 'tampered' WHERE id = :id"), {"id": event.id})
    with pytest.raises(DBAPIError):
        with db_session.begin_nested():
            db_session.execute(text("DELETE FROM audit_events WHERE id = :id"), {"id": event.id})

