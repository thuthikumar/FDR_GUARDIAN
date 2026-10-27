from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.api.dashboard_reports import _csv_safe, _today, maturity_bucket
from app.core.config import maturity_thresholds
from app.core.permissions import Permission, permissions_for_role
from app.models import Alert, AuditEvent, VerificationCase
from app.models.enums import AlertSeverity, AlertStatus, UserRole, WorkflowStatus
from app.models.workflow import VerificationCase as Case
from test_registry_api import add_fdr, add_institution, add_user, auth


@pytest.mark.parametrize(("days", "label"), [(-1, "overdue-date review"), (-10, "overdue-date review"), (0, "urgent"), (7, "urgent"), (8, "attention"), (30, "attention"), (31, "upcoming"), (90, "upcoming"), (91, "normal")])
def test_maturity_bucket_boundaries(days, label):
    assert maturity_bucket(days) == label


def test_dashboard_today_uses_injectable_kolkata_timezone():
    from datetime import datetime, timezone
    assert _today(datetime(2026, 1, 1, 20, 0, tzinfo=timezone.utc)) == date(2026, 1, 2)


def test_maturity_thresholds_are_configurable(monkeypatch):
    monkeypatch.setenv("MATURITY_URGENT_DAYS", "5")
    monkeypatch.setenv("MATURITY_ATTENTION_DAYS", "20")
    monkeypatch.setenv("MATURITY_UPCOMING_DAYS", "75")
    assert maturity_thresholds() == (5, 20, 75)


@pytest.mark.parametrize("value", ["=cmd", "+cmd", "-cmd", "@cmd", "\tcmd", "\rcmd"])
def test_csv_formula_injection_is_escaped(value):
    assert _csv_safe(value) == "'" + value


def test_dashboard_reports_scope_metrics_and_csv_audit(api_client, db_session):
    from app.models.enums import FDRRecordStatus, VerificationStatus

    a = add_institution(db_session, code="RPT-A", name="Synthetic A")
    b = add_institution(db_session, code="RPT-B", name="Synthetic B")
    today = date.today()
    a_active = add_fdr(db_session, a, internal_fdr_id="RPT-ACTIVE", amount=Decimal("1234.00"), maturity_date=today + timedelta(days=7), bank_name="=HYPERLINK(\"x\")")
    add_fdr(db_session, a, internal_fdr_id="RPT-PAST", maturity_date=today - timedelta(days=2), record_status=FDRRecordStatus.MATURED.value)
    b_record = add_fdr(db_session, b, internal_fdr_id="RPT-B", maturity_date=today + timedelta(days=30))
    db_session.add_all([
        Case(fdr_record_id=a_active.id, status=WorkflowStatus.SUBMITTED.value, reason="Synthetic pending case"),
        Case(fdr_record_id=b_record.id, status=WorkflowStatus.UNDER_REVIEW.value, reason="Synthetic other case"),
        Alert(fdr_record_id=a_active.id, alert_type="synthetic_demo", severity=AlertSeverity.LOW.value, explanation="Synthetic alert", status=AlertStatus.OPEN.value),
    ])
    db_session.flush()
    admin = add_user(db_session, UserRole.INSTITUTION_ADMIN.value, a.id)
    summary = api_client.get("/api/v1/dashboard/summary", headers=auth(admin))
    assert summary.status_code == 200
    assert summary.json() == {"total_institutions": 1, "total_fdr_records": 2, "active_records": 1,
        "upcoming_maturities": 1, "overdue_date_review": 0, "pending_verification_cases": 1, "unresolved_alerts": 1}
    chart = api_client.get("/api/v1/dashboard/charts", headers=auth(admin)).json()
    assert chart["institution_distribution"][0]["label"] == "Synthetic A"
    assert chart["institution_distribution"][0]["count"] == 2
    rows = api_client.get("/api/v1/reports/maturities", headers=auth(admin)).json()
    assert rows["total"] == 2 and all(row["institution_id"] == str(a.id) for row in rows["items"])
    institution_rows = api_client.get("/api/v1/reports/institution-summary", headers=auth(admin)).json()
    assert institution_rows["total"] == 1 and institution_rows["items"][0]["total_principal"] == "2234.00"
    assert api_client.get(f"/api/v1/reports/maturities?institution_id={b.id}", headers=auth(admin)).json()["total"] == 2
    assert api_client.get("/api/v1/reports/maturities?page=0", headers=auth(admin)).status_code == 422
    assert api_client.get("/api/v1/reports/maturities?sort_by=secret", headers=auth(admin)).status_code == 422
    assert api_client.get("/api/v1/reports/maturities?format=csv", headers=auth(admin)).status_code == 403

    auditor = add_user(db_session, UserRole.READ_ONLY_AUDITOR.value)
    exported = api_client.get(f"/api/v1/reports/maturities?format=csv&institution_id={a.id}", headers=auth(auditor))
    assert exported.status_code == 200 and exported.content.startswith(b"\xef\xbb\xbf")
    body = exported.content.decode("utf-8-sig")
    assert "Data source,synthetic demo" in body and "Internal FDR ID" in body
    assert "'=HYPERLINK" in body and "RPT-B" not in body and "institution_id" not in body
    event = db_session.scalar(select(AuditEvent).where(AuditEvent.action == "report_csv_exported"))
    assert event and event.actor_id == auditor.id and event.change_summary["row_count"] == 2
    assert set(event.change_summary) == {"report_name", "filters", "row_count"}
    summary_csv = api_client.get("/api/v1/reports/institution-summary?format=csv", headers=auth(auditor))
    assert summary_csv.status_code == 200 and summary_csv.content.startswith(b"\xef\xbb\xbf")


def test_dashboard_report_permission_matrix(api_client, db_session):
    for role in UserRole:
        user = add_user(db_session, role.value, None if role != UserRole.INSTITUTION_ADMIN else add_institution(db_session, code=f"MATRIX-{role.value}" ).id)
        expected = 200 if Permission.REPORT_READ in permissions_for_role(role.value) else 403
        assert api_client.get("/api/v1/dashboard/summary", headers=auth(user)).status_code == expected
        assert api_client.get("/api/v1/dashboard/charts", headers=auth(user)).status_code == expected
        assert api_client.get("/api/v1/reports/institution-summary", headers=auth(user)).status_code == expected
        assert api_client.get("/api/v1/reports/maturities", headers=auth(user)).status_code == expected
        assert api_client.get("/api/v1/reports/maturities?format=csv", headers=auth(user)).status_code == (200 if Permission.REPORT_READ in permissions_for_role(role.value) and Permission.REPORT_EXPORT in permissions_for_role(role.value) else 403)
