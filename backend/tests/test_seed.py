from collections import Counter
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

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
from app.models.enums import ApprovalDecision, ReviewStatus, UserRole, WorkflowStatus
from app.seed import FDR_RECORD_COUNT, INSTITUTION_COUNT, SCENARIO_RECORD_IDS, seed_synthetic_data


ALL_MODELS = (
    User,
    Institution,
    FDRRecord,
    Document,
    ExtractedField,
    VerificationCase,
    ApprovalAction,
    ReleaseEvent,
    Alert,
    Notification,
    AuditEvent,
    IntegrationSyncRun,
)


def _counts(session: Session) -> dict[str, int]:
    return {
        model.__tablename__: session.scalar(select(func.count()).select_from(model)) or 0
        for model in ALL_MODELS
    }


def test_seed_is_idempotent_and_has_expected_volume(db_session: Session) -> None:
    reference_date = date(2026, 10, 24)
    first_report = seed_synthetic_data(db_session, reference_date)
    first_counts = _counts(db_session)
    second_report = seed_synthetic_data(db_session, reference_date)
    second_counts = _counts(db_session)

    assert first_report == second_report
    assert first_counts == second_counts
    assert first_counts["institutions"] == INSTITUTION_COUNT == 10
    assert first_counts["fdr_records"] == FDR_RECORD_COUNT == 100
    assert first_counts["users"] == 16


def test_seed_covers_all_scenarios_and_labels_every_primary_record_synthetic(db_session: Session) -> None:
    seed_synthetic_data(db_session, date(2026, 10, 24))
    assert len(SCENARIO_RECORD_IDS) == 14

    scenario_ids = {internal_id for group in SCENARIO_RECORD_IDS.values() for internal_id in group}
    records = list(db_session.scalars(select(FDRRecord).where(FDRRecord.internal_fdr_id.in_(scenario_ids))))
    assert scenario_ids <= {record.internal_fdr_id for record in records}
    assert all(record.is_synthetic for record in records)
    assert all(user.is_synthetic and user.password_hash is None for user in db_session.scalars(select(User)))
    assert all(institution.is_synthetic for institution in db_session.scalars(select(Institution)))
    assert db_session.scalar(select(func.count()).select_from(FDRRecord).where(FDRRecord.is_synthetic.is_(False))) == 0

    valid_record = next(record for record in records if record.internal_fdr_id == "SYN-FDR-0001")
    valid_document = db_session.scalar(select(Document).where(Document.fdr_record_id == valid_record.id))
    assert valid_document is not None
    assert valid_document.review_status == ReviewStatus.ACCEPTED.value
    reviewed_field = db_session.scalar(
        select(ExtractedField).where(
            ExtractedField.document_id == valid_document.id,
            ExtractedField.field_name == "bank_name",
        )
    )
    assert reviewed_field.reviewer_confirmed_value == reviewed_field.extracted_value

    roles = Counter(user.role for user in db_session.scalars(select(User)))
    assert roles == {
        UserRole.SYSTEM_ADMIN.value: 1,
        UserRole.INSTITUTION_ADMIN.value: INSTITUTION_COUNT,
        UserRole.VERIFICATION_OFFICER.value: 2,
        UserRole.ACCOUNTS_OFFICER.value: 1,
        UserRole.FINAL_APPROVER.value: 1,
        UserRole.READ_ONLY_AUDITOR.value: 1,
    }


def test_scenario_rows_match_document_workflow_and_release_rules(db_session: Session) -> None:
    seed_synthetic_data(db_session, date(2026, 10, 24))
    by_internal_id = {
        record.internal_fdr_id: record
        for record in db_session.scalars(select(FDRRecord))
    }

    duplicate_ids = SCENARIO_RECORD_IDS["duplicate_identifier"]
    assert by_internal_id[duplicate_ids[0]].fdr_number == by_internal_id[duplicate_ids[1]].fdr_number
    assert by_internal_id[duplicate_ids[0]].institution_id == by_internal_id[duplicate_ids[1]].institution_id
    assert by_internal_id["SYN-FDR-0002"].maturity_date > date(2026, 10, 24)
    assert by_internal_id["SYN-FDR-0003"].maturity_date < date(2026, 10, 24)

    missing_document_record = by_internal_id["SYN-FDR-0004"]
    assert db_session.scalar(select(func.count()).select_from(Document).where(Document.fdr_record_id == missing_document_record.id)) == 0
    assert all(document.private_storage_key.startswith("synthetic/") for document in db_session.scalars(select(Document)))

    amount_doc = db_session.scalar(select(Document).where(Document.fdr_record_id == by_internal_id["SYN-FDR-0005"].id))
    amount_field = db_session.scalar(select(ExtractedField).where(ExtractedField.document_id == amount_doc.id, ExtractedField.field_name == "amount"))
    assert Decimal(amount_field.extracted_value) != by_internal_id["SYN-FDR-0005"].amount
    number_doc = db_session.scalar(select(Document).where(Document.fdr_record_id == by_internal_id["SYN-FDR-0006"].id))
    number_field = db_session.scalar(select(ExtractedField).where(ExtractedField.document_id == number_doc.id, ExtractedField.field_name == "fdr_number"))
    assert number_field.extracted_value != by_internal_id["SYN-FDR-0006"].fdr_number
    date_doc = db_session.scalar(select(Document).where(Document.fdr_record_id == by_internal_id["SYN-FDR-0007"].id))
    date_field = db_session.scalar(select(ExtractedField).where(ExtractedField.document_id == date_doc.id, ExtractedField.field_name == "maturity_date"))
    assert date.fromisoformat(date_field.extracted_value) != by_internal_id["SYN-FDR-0007"].maturity_date

    uncertain_document = db_session.scalar(
        select(Document).where(Document.fdr_record_id == by_internal_id["SYN-FDR-0009"].id)
    )
    uncertain_fields = list(
        db_session.scalars(select(ExtractedField).where(ExtractedField.document_id == uncertain_document.id))
    )
    assert any(field.confidence_score is None for field in uncertain_fields)
    assert any(field.confidence_score is not None and field.confidence_score < 0.5 for field in uncertain_fields)

    cases = {case.fdr_record_id: case for case in db_session.scalars(select(VerificationCase))}
    assert cases[by_internal_id["SYN-FDR-0010"].id].status == WorkflowStatus.SUBMITTED.value
    assert cases[by_internal_id["SYN-FDR-0011"].id].status == WorkflowStatus.MORE_INFORMATION_REQUIRED.value
    rejected_case = cases[by_internal_id["SYN-FDR-0012"].id]
    assert rejected_case.status == WorkflowStatus.REJECTED.value
    assert "rejection" in rejected_case.reason.lower()
    rejected_action = db_session.scalar(select(ApprovalAction).where(ApprovalAction.case_id == rejected_case.id))
    assert rejected_action.decision == ApprovalDecision.REJECTED.value
    assert "rejection" in rejected_action.remarks.lower()

    approved_record = by_internal_id["SYN-FDR-0013"]
    approved_case = cases[approved_record.id]
    assert approved_case.status == WorkflowStatus.APPROVED.value
    assert db_session.scalar(select(func.count()).select_from(ReleaseEvent).where(ReleaseEvent.fdr_record_id == approved_record.id)) == 0
    approved_action = db_session.scalar(select(ApprovalAction).where(ApprovalAction.case_id == approved_case.id))
    assert approved_action.decision == ApprovalDecision.APPROVED.value

    released_record = by_internal_id["SYN-FDR-0014"]
    release_event = db_session.scalar(select(ReleaseEvent).where(ReleaseEvent.fdr_record_id == released_record.id))
    assert release_event is not None and release_event.is_demo is True


def test_seed_has_both_resolved_and_unresolved_alerts(db_session: Session) -> None:
    seed_synthetic_data(db_session, date(2026, 10, 24))
    statuses = set(db_session.scalars(select(Alert.status)))
    assert "resolved" in statuses
    assert "open" in statuses or "acknowledged" in statuses
