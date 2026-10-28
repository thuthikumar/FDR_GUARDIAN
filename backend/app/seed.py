"""Deterministic, idempotent synthetic data seed command."""

from __future__ import annotations

import argparse
import random
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import UUID, NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import make_engine
from app.models import (
    Alert,
    ApprovalAction,
    AuditEvent,
    Document,
    ExtractedField,
    FDRRecord,
    Institution,
    IntegrationSyncRun,
    Notification,
    ReleaseEvent,
    User,
    VerificationCase,
)
from app.models.enums import (
    AlertSeverity,
    AlertStatus,
    ApprovalActionType,
    ApprovalDecision,
    DocumentType,
    FDRRecordStatus,
    InstitutionStatus,
    NotificationType,
    ProcessingStatus,
    ReviewStatus,
    SyncRunStatus,
    UserRole,
    VerificationStatus,
    WorkflowStatus,
)


SOURCE_SYSTEM = "SYNTHETIC_DEMO"
RANDOM_SEED = 26265
INSTITUTION_COUNT = 10
FDR_RECORD_COUNT = 100

# Stable identifiers make scenario-oriented tests and demos easy to discover.
SCENARIO_RECORD_IDS: dict[str, tuple[str, ...]] = {
    "valid_looking_demo_fdr": ("SYN-FDR-0001",),
    "upcoming_maturity": ("SYN-FDR-0002",),
    "maturity_in_past": ("SYN-FDR-0003",),
    "missing_required_document": ("SYN-FDR-0004",),
    "amount_mismatch": ("SYN-FDR-0005",),
    "fdr_number_mismatch": ("SYN-FDR-0006",),
    "maturity_date_mismatch": ("SYN-FDR-0007",),
    "duplicate_identifier": ("SYN-FDR-0008", "SYN-FDR-0009"),
    "ocr_uncertainty": ("SYN-FDR-0009",),
    "pending_verification": ("SYN-FDR-0010",),
    "additional_information_requested": ("SYN-FDR-0011",),
    "rejected_with_reason": ("SYN-FDR-0012",),
    "approved_without_release": ("SYN-FDR-0013",),
    "confirmed_demo_release": ("SYN-FDR-0014",),
}


def _stable_id(table: str, key: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"fdr-guardian:{table}:{key}")


def _upsert(
    session: Session,
    model: type,
    lookup: dict[str, object],
    values: dict[str, object],
    stable_key: str,
):
    row = session.scalar(select(model).filter_by(**lookup))
    if row is None:
        row = model(id=_stable_id(model.__tablename__, stable_key), **lookup, **values)
        session.add(row)
    else:
        for name, value in values.items():
            setattr(row, name, value)
    session.flush()
    return row


def _upsert_stable(session: Session, model: type, stable_key: str, values: dict[str, object]):
    row_id = _stable_id(model.__tablename__, stable_key)
    row = session.get(model, row_id)
    if row is None:
        row = model(id=row_id, **values)
        session.add(row)
    else:
        for name, value in values.items():
            setattr(row, name, value)
    session.flush()
    return row


def _insert_stable(session: Session, model: type, stable_key: str, values: dict[str, object]):
    """Insert an append-only row once; never rewrite historical actions/events."""
    row_id = _stable_id(model.__tablename__, stable_key)
    row = session.get(model, row_id)
    if row is None:
        row = model(id=row_id, **values)
        session.add(row)
        session.flush()
    return row


def _demo_users(session: Session, institutions: list[Institution]) -> dict[str, User]:
    specs: list[tuple[str, str, UserRole, Institution | None]] = [
        ("system-admin@synthetic.invalid", "Synthetic System Administrator", UserRole.SYSTEM_ADMIN, None),
        ("verification-01@synthetic.invalid", "Synthetic Verification Officer 01", UserRole.VERIFICATION_OFFICER, None),
        ("verification-02@synthetic.invalid", "Synthetic Verification Officer 02", UserRole.VERIFICATION_OFFICER, None),
        ("accounts-01@synthetic.invalid", "Synthetic Accounts Officer 01", UserRole.ACCOUNTS_OFFICER, None),
        ("approver-01@synthetic.invalid", "Synthetic Final Approver 01", UserRole.FINAL_APPROVER, None),
        ("auditor-01@synthetic.invalid", "Synthetic Read-only Auditor 01", UserRole.READ_ONLY_AUDITOR, None),
    ]
    for index, institution in enumerate(institutions, start=1):
        specs.append((
            f"institution-{index:03d}-admin@synthetic.invalid",
            f"Synthetic Institution Administrator {index:03d}",
            UserRole.INSTITUTION_ADMIN,
            institution,
        ))

    users: dict[str, User] = {}
    for email, full_name, role, institution in specs:
        users[email] = _upsert(
            session,
            User,
            {"email": email},
            {
                "full_name": full_name,
                "password_hash": None,
                "role": role.value,
                "institution_id": institution.id if institution else None,
                "is_active": True,
                "is_synthetic": True,
            },
            email,
        )
    return users


def _case_scenarios(reference_date: date) -> dict[int, dict[str, object]]:
    opened_at = datetime.combine(reference_date - timedelta(days=2), time(9), tzinfo=timezone.utc)
    closed_at = datetime.combine(reference_date - timedelta(days=1), time(15), tzinfo=timezone.utc)
    return {
        10: {"status": WorkflowStatus.SUBMITTED, "reason": "Synthetic record awaiting verification.", "closed_at": None},
        11: {"status": WorkflowStatus.MORE_INFORMATION_REQUIRED, "reason": "Synthetic reviewer requested a missing supporting detail.", "closed_at": None},
        12: {"status": WorkflowStatus.REJECTED, "reason": "Synthetic rejection: submitted dates are inconsistent and require resubmission.", "closed_at": closed_at},
        13: {"status": WorkflowStatus.APPROVED, "reason": "Synthetic approval recorded; no release event is present.", "closed_at": closed_at},
        14: {"status": WorkflowStatus.RELEASED, "reason": "Synthetic release event explicitly recorded for demonstration.", "closed_at": closed_at},
    }


def seed_synthetic_data(session: Session, reference_date: date | None = None) -> dict[str, int]:
    """Insert or update the fixed demo dataset without duplicating rows."""
    from app.services.monitoring import ensure_default_maturity_rules

    ensure_default_maturity_rules(session)
    reference_date = reference_date or date.today()
    rng = random.Random(RANDOM_SEED)
    today_utc = datetime.combine(reference_date, time.min, tzinfo=timezone.utc)

    institutions = [
        _upsert(
            session,
            Institution,
            {"institution_code": f"SYN-INST-{number:03d}"},
            {
                "institution_name": f"SYNTHETIC Institute of Technology {chr(64 + number)}",
                "institution_type": "Synthetic technical institution",
                "state": f"Synthetic State {((number - 1) % 5) + 1}",
                "contact_email": f"contact-{number:03d}@synthetic.invalid",
                "status": InstitutionStatus.ACTIVE.value,
                "is_synthetic": True,
            },
            f"SYN-INST-{number:03d}",
        )
        for number in range(1, INSTITUTION_COUNT + 1)
    ]
    users = _demo_users(session, institutions)
    admin = users["system-admin@synthetic.invalid"]
    verifier_1 = users["verification-01@synthetic.invalid"]
    verifier_2 = users["verification-02@synthetic.invalid"]
    approver = users["approver-01@synthetic.invalid"]
    auditor = users["auditor-01@synthetic.invalid"]

    scenario_days = {1: 365, 2: 25, 3: -10, 4: 120, 5: 60, 6: 85, 7: 45, 8: 200, 9: 150, 10: 95, 11: 50, 12: 180, 13: 240, 14: 300}
    scenario_verification = {
        1: VerificationStatus.VERIFIED,
        2: VerificationStatus.UNDER_REVIEW,
        3: VerificationStatus.NOT_SUBMITTED,
        4: VerificationStatus.SUBMITTED,
        5: VerificationStatus.UNDER_REVIEW,
        6: VerificationStatus.UNDER_REVIEW,
        7: VerificationStatus.UNDER_REVIEW,
        8: VerificationStatus.NOT_SUBMITTED,
        9: VerificationStatus.UNDER_REVIEW,
        10: VerificationStatus.SUBMITTED,
        11: VerificationStatus.MORE_INFORMATION_REQUIRED,
        12: VerificationStatus.REJECTED,
        13: VerificationStatus.APPROVED,
        14: VerificationStatus.RELEASED,
    }
    records: dict[int, FDRRecord] = {}
    for number in range(1, FDR_RECORD_COUNT + 1):
        institution_index = 7 if number == 9 else (number - 1) % INSTITUTION_COUNT
        institution = institutions[institution_index]
        days_until_maturity = scenario_days.get(number, rng.choice([-15, -2, 5, 18, 40, 75, 120, 210, 320]))
        issue_date = reference_date - timedelta(days=rng.randint(420, 1000))
        maturity_date = reference_date + timedelta(days=days_until_maturity)
        status = FDRRecordStatus.MATURED if days_until_maturity < 0 else FDRRecordStatus.ACTIVE
        generated_verification_states = [
            state for state in VerificationStatus if state != VerificationStatus.RELEASED
        ]
        verify_status = scenario_verification.get(number, rng.choice(generated_verification_states))
        internal_id = f"SYN-FDR-{number:04d}"
        fdr_number = "SYNTH-FDR-DUPLICATE-0008-0009" if number in (8, 9) else f"SYNTH-FDR-{number:04d}"
        if number == 14:
            status = FDRRecordStatus.RELEASED
        record = _upsert(
            session,
            FDRRecord,
            {"internal_fdr_id": internal_id},
            {
                "institution_id": institution.id,
                "external_record_id": None,
                "bank_name": f"Synthetic Community Bank {((number - 1) % 7) + 1:02d}",
                "branch_name": f"Synthetic Branch {((number - 1) % 10) + 1:03d}",
                "fdr_number": fdr_number,
                "amount": Decimal(rng.randrange(100_000, 5_000_000)).quantize(Decimal("0.01")),
                "currency": "INR",
                "issue_date": issue_date,
                "maturity_date": maturity_date,
                "record_status": status.value,
                "verification_status": verify_status.value,
                "source_system": SOURCE_SYSTEM,
                "source_updated_at": today_utc,
                "last_synced_at": today_utc,
                "is_synthetic": True,
            },
            internal_id,
        )
        records[number] = record

    # Metadata-only fixtures: no files are written to disk in Phase 2.
    document_by_record: dict[int, Document] = {}
    for number, record in records.items():
        if number == 4:  # scenario 4 intentionally has no required document
            continue
        storage_key = f"synthetic/{record.internal_fdr_id}/demo-certificate-metadata"
        document = _upsert(
            session,
            Document,
            {"private_storage_key": storage_key},
            {
                "fdr_record_id": record.id,
                "document_type": DocumentType.FDR_CERTIFICATE.value,
                "original_filename": "synthetic-fdr-certificate-metadata.pdf",
                "content_type": "application/pdf",
                "file_size": 1,
                "checksum": None,
                "uploaded_by": admin.id,
                "processing_status": ProcessingStatus.PROCESSED.value,
                "review_status": ReviewStatus.PENDING.value if number == 9 else ReviewStatus.ACCEPTED.value,
            },
            storage_key,
        )
        document_by_record[number] = document

    extracted: dict[int, list[tuple[str, str | None, Decimal | None, str | None]]] = {
        5: [("amount", "1.00", Decimal("0.990"), None)],
        6: [("fdr_number", "SYNTH-FDR-DOCUMENT-MISMATCH-0006", Decimal("0.870"), None)],
        7: [("maturity_date", (reference_date + timedelta(days=12)).isoformat(), Decimal("0.810"), None)],
        9: [("fdr_number", None, None, None), ("amount", str(records[9].amount), Decimal("0.210"), None)],
        1: [("bank_name", records[1].bank_name, Decimal("0.980"), records[1].bank_name)],
    }
    for number, fields in extracted.items():
        document = document_by_record[number]
        for field_name, value, confidence, confirmed in fields:
            _upsert(
                session,
                ExtractedField,
                {"document_id": document.id, "field_name": field_name},
                {
                    "extracted_value": value,
                    "confidence_score": confidence,
                    "extraction_method": "synthetic_fixture",
                    "reviewer_confirmed_value": confirmed,
                    "reviewed_by": admin.id if confirmed is not None else None,
                    "reviewed_at": today_utc if confirmed is not None else None,
                },
                f"{document.id}:{field_name}",
            )

    case_specs = _case_scenarios(reference_date)
    cases: dict[int, VerificationCase] = {}
    case_assignees: dict[int, User | None] = {10: None, 11: verifier_2, 12: verifier_1, 13: verifier_1, 14: verifier_2}
    for number, spec in case_specs.items():
        case = _upsert_stable(
            session,
            VerificationCase,
            f"seed-scenario-{number:02d}",
            {
                "fdr_record_id": records[number].id,
                "assigned_officer_id": case_assignees[number].id if case_assignees[number] else None,
                "status": spec["status"].value,
                "priority": "high" if number in (10, 11, 12) else "normal",
                "reason": spec["reason"],
                "opened_at": today_utc - timedelta(days=2),
                "updated_at": today_utc,
                "closed_at": spec["closed_at"],
            },
        )
        cases[number] = case

    action_specs = {
        10: (ApprovalActionType.SUBMITTED, ApprovalDecision.NONE, WorkflowStatus.DRAFT, WorkflowStatus.SUBMITTED, "Synthetic record submitted for verification."),
        11: (ApprovalActionType.REQUESTED_INFORMATION, ApprovalDecision.MORE_INFORMATION_REQUIRED, VerificationStatus.UNDER_REVIEW, VerificationStatus.MORE_INFORMATION_REQUIRED, "Synthetic request for additional information."),
        12: (ApprovalActionType.REJECTED, ApprovalDecision.REJECTED, VerificationStatus.UNDER_REVIEW, VerificationStatus.REJECTED, "Synthetic rejection: submitted dates are inconsistent and require resubmission."),
        13: (ApprovalActionType.APPROVED, ApprovalDecision.APPROVED, VerificationStatus.PENDING_APPROVAL, VerificationStatus.APPROVED, "Synthetic approval; release has not been confirmed."),
        14: (ApprovalActionType.RELEASE_RECORDED, ApprovalDecision.RELEASE_RECORDED, VerificationStatus.RELEASE_PENDING, VerificationStatus.RELEASED, "Synthetic release event recorded for demonstration."),
    }
    for number, (action, decision, from_status, to_status, remarks) in action_specs.items():
        actor = approver if number in (13, 14) else (verifier_2 if number in (11, 14) else verifier_1)
        _insert_stable(
            session,
            ApprovalAction,
            f"scenario-action-{number:02d}",
            {
                "case_id": cases[number].id,
                "actor_id": actor.id,
                "action_type": action.value,
                "decision": decision.value,
                "from_status": from_status.value,
                "to_status": to_status.value,
                "remarks": remarks,
                "created_at": today_utc,
            },
        )

    _insert_stable(
        session,
        ReleaseEvent,
        "scenario-release-14",
        {
            "case_id": cases[14].id,
            "fdr_record_id": records[14].id,
            "recorded_by": approver.id,
            "released_at": today_utc,
            "release_reference": "SYNTHETIC-RELEASE-0014",
            "remarks": "Synthetic demonstration event only; not a real bank transaction.",
            "is_demo": True,
        },
    )

    alert_specs = [
        (2, "maturity_upcoming", AlertSeverity.HIGH, AlertStatus.OPEN, "Synthetic FDR matures within 30 days."),
        (3, "maturity_overdue_review", AlertSeverity.MEDIUM, AlertStatus.RESOLVED, "Synthetic maturity date is in the past; manual review is required."),
        (5, "amount_mismatch", AlertSeverity.HIGH, AlertStatus.OPEN, "Synthetic extracted amount differs from the stored value."),
        (6, "fdr_number_mismatch", AlertSeverity.MEDIUM, AlertStatus.ACKNOWLEDGED, "Synthetic extracted FDR number differs from the stored value."),
        (7, "maturity_date_mismatch", AlertSeverity.MEDIUM, AlertStatus.RESOLVED, "Synthetic extracted maturity date differs from the stored value."),
        (8, "duplicate_identifier", AlertSeverity.HIGH, AlertStatus.OPEN, "Synthetic FDR number is shared by two demo records."),
        (9, "duplicate_identifier", AlertSeverity.HIGH, AlertStatus.ACKNOWLEDGED, "Synthetic FDR number is shared by two demo records."),
    ]
    alert_count = 0
    for number, alert_type, severity, status, explanation in alert_specs:
        alert_id_key = f"scenario-alert-{number:04d}-{alert_type}"
        created_at = today_utc - timedelta(days=3)
        resolved = status == AlertStatus.RESOLVED
        seed_source = "system_rule" if alert_type == "maturity_upcoming" and status in (AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED) else "legacy_seed"
        seed_rule = "maturity_upcoming" if seed_source == "system_rule" else None
        _insert_stable(
            session,
            Alert,
            alert_id_key,
            {
                "fdr_record_id": records[number].id,
                "alert_type": alert_type,
                "severity": severity.value,
                "explanation": explanation,
                "status": status.value,
                "source": seed_source,
                "rule_key": seed_rule,
                "details": {"legacy_seeded": True, "maturity_date": records[number].maturity_date.isoformat()},
                "created_at": created_at,
                "resolved_at": today_utc if resolved else None,
                "resolved_by": auditor.id if resolved else None,
            },
        )
        alert_count += 1
        recipient = users[f"institution-{((number - 1) % INSTITUTION_COUNT) + 1:03d}-admin@synthetic.invalid"]
        _upsert_stable(
            session,
            Notification,
            f"seed-alert-notification-{number:04d}-{alert_type}",
            {
                "recipient_user_id": recipient.id,
                "notification_type": NotificationType.MATURITY_ALERT.value if alert_type.startswith("maturity") else NotificationType.DISCREPANCY.value,
                "title": f"Synthetic alert: {alert_type.replace('_', ' ')}",
                "message": explanation,
                "related_record_id": records[number].id,
                "read_at": today_utc if resolved else None,
                "created_at": created_at,
            },
        )

    for number, record in records.items():
        _insert_stable(
            session,
            AuditEvent,
            f"synthetic-seed-fdr-{number:04d}",
            {
                "actor_id": admin.id,
                "action": "synthetic_seeded",
                "entity_type": "fdr_record",
                "entity_id": record.id,
                "timestamp": today_utc,
                "correlation_id": f"synthetic-seed-{reference_date.isoformat()}",
                "change_summary": {"source_system": SOURCE_SYSTEM, "is_synthetic": True},
            },
        )

    _upsert_stable(
        session,
        IntegrationSyncRun,
        "synthetic-demo-seed-run",
        {
            "source_name": SOURCE_SYSTEM,
            "started_at": today_utc,
            "completed_at": today_utc,
            "status": SyncRunStatus.SUCCEEDED.value,
            "records_read": FDR_RECORD_COUNT,
            "records_created": FDR_RECORD_COUNT,
            "records_updated": 0,
            "records_skipped": 0,
            "errors_summary": [],
        },
    )
    session.flush()
    return {
        "institutions": len(institutions),
        "users": len(users),
        "fdr_records": len(records),
        "documents": len(document_by_record),
        "alerts": alert_count,
        "verification_cases": len(cases),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed clearly labelled synthetic FDR Guardian data.")
    parser.add_argument("--reference-date", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    engine = make_engine()
    try:
        with Session(engine) as session, session.begin():
            counts = seed_synthetic_data(session, args.reference_date)
        print(f"Synthetic seed completed for reference date {args.reference_date.isoformat()}: {counts}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
