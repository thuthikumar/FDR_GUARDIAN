from datetime import date, datetime, timedelta
from threading import Event, Thread
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from app.core.permissions import Permission, permissions_for_role
from app.models import Alert, AuditEvent, MonitoringJobRun
from app.models.enums import AlertSeverity, AlertStatus, UserRole
from app.services.monitoring import RuleBand, evaluate_maturities, select_rule_band, validate_rule_set
from test_registry_api import add_fdr, add_institution, add_user, auth


def bands():
    return [
        RuleBand("past", "maturity_overdue_date_review", "Overdue-date review", None, -1, "high"),
        RuleBand("urgent", "maturity_urgent", "Urgent", 0, 7, "high"),
        RuleBand("attention", "maturity_attention_required", "Attention required", 8, 30, "medium"),
        RuleBand("upcoming", "maturity_upcoming", "Upcoming", 31, 90, "low"),
        RuleBand("normal", "maturity_normal", "Normal", 91, None, "low"),
    ]


@pytest.mark.parametrize(("days", "key"), [(91,"normal"),(90,"upcoming"),(31,"upcoming"),(30,"attention"),(8,"attention"),(7,"urgent"),(0,"urgent"),(-1,"past")])
def test_rule_band_boundaries(days, key):
    assert select_rule_band(bands(), days).rule_key == key


@pytest.mark.parametrize("rules", [
    [RuleBand("past","x","x",None,-1,"high"), RuleBand("a","a","a",0,7,"high"), RuleBand("b","b","b",9,30,"medium"), RuleBand("c","c","c",31,90,"low"), RuleBand("d","d","d",91,None,"low")],
    [RuleBand("past","x","x",None,-1,"high"), RuleBand("a","a","a",0,8,"high"), RuleBand("b","b","b",8,30,"medium"), RuleBand("c","c","c",31,90,"low"), RuleBand("d","d","d",91,None,"low")],
    [RuleBand("past","x","x",None,-1,"high"), RuleBand("a","a","a",-1,7,"high"), RuleBand("b","b","b",8,30,"medium"), RuleBand("c","c","c",31,90,"low"), RuleBand("d","d","d",91,None,"low")],
])
def test_rule_validation_rejects_gap_overlap_and_negative(rules):
    with pytest.raises(ValueError):
        validate_rule_set(rules)


def test_monitoring_lifecycle_idempotency_transition_auto_resolve_and_reopen(db_session):
    tz = ZoneInfo("Asia/Kolkata")
    reference = datetime(2026, 11, 1, 12, tzinfo=tz)
    institution = add_institution(db_session)
    record = add_fdr(db_session, institution, maturity_date=reference.date() + timedelta(days=12))
    first = evaluate_maturities(db_session, reference_datetime=reference, trigger="manual")
    first_alert = db_session.scalar(select(Alert).where(Alert.fdr_record_id == record.id, Alert.source == "system_rule", Alert.status == "open"))
    assert first.status == "success" and first.alerts_created == 1
    assert first_alert.rule_key == "maturity_attention_required"
    second = evaluate_maturities(db_session, reference_datetime=reference, trigger="manual")
    assert second.alerts_created == 0 and second.alerts_unchanged == 1
    assert db_session.scalar(select(func.count()).select_from(Alert).where(Alert.fdr_record_id == record.id, Alert.status.in_(["open","acknowledged"]))) == 1

    record.maturity_date = reference.date() + timedelta(days=5)
    moved = evaluate_maturities(db_session, reference_datetime=reference)
    assert moved.alerts_superseded == 1 and moved.alerts_created == 1
    urgent = db_session.scalar(select(Alert).where(Alert.fdr_record_id == record.id, Alert.status == "open"))
    urgent_date = record.maturity_date
    record.maturity_date = reference.date() + timedelta(days=120)
    extended = evaluate_maturities(db_session, reference_datetime=reference)
    assert extended.alerts_resolved == 1
    auto_resolved = db_session.scalar(select(Alert).where(Alert.id == urgent.id))
    assert auto_resolved.resolution_type == "auto"
    record.maturity_date = urgent_date
    reopened = evaluate_maturities(db_session, reference_datetime=reference)
    assert reopened.alerts_reopened == 1
    assert db_session.scalar(select(Alert).where(Alert.id == urgent.id)).status == "open"
    assert db_session.scalar(select(func.count()).select_from(MonitoringJobRun)) == 5
    assert db_session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "monitoring_run_completed")) == 5


def test_manual_resolve_blocks_same_snapshot_but_changed_date_creates_new_alert(api_client, db_session):
    reference = datetime(2026, 11, 1, 12, tzinfo=ZoneInfo("Asia/Kolkata"))
    institution = add_institution(db_session)
    record = add_fdr(db_session, institution, maturity_date=reference.date() + timedelta(days=2))
    admin = add_user(db_session, UserRole.SYSTEM_ADMIN.value)
    officer = add_user(db_session, UserRole.VERIFICATION_OFFICER.value)
    evaluate_maturities(db_session, reference_datetime=reference)
    alert = db_session.scalar(select(Alert).where(Alert.fdr_record_id == record.id, Alert.source == "system_rule", Alert.status == "open"))
    response = api_client.post(f"/api/v1/alerts/{alert.id}/resolve", json={"remarks":"Synthetic manual review"}, headers=auth(officer))
    assert response.status_code == 200
    assert api_client.post(f"/api/v1/alerts/{alert.id}/resolve", json={"remarks":"double"}, headers=auth(officer)).status_code == 409
    assert api_client.post(f"/api/v1/alerts/{alert.id}/resolve", json={"remarks":" "}, headers=auth(officer)).status_code == 422
    same = evaluate_maturities(db_session, reference_datetime=reference)
    assert same.alerts_created == 0
    record.maturity_date += timedelta(days=1)
    fresh = evaluate_maturities(db_session, reference_datetime=reference)
    assert fresh.alerts_created == 1
    assert db_session.scalar(select(Alert).where(Alert.fdr_record_id == record.id, Alert.status == "open")) is not None
    assert Permission.ALERT_MANAGE in permissions_for_role(officer.role)
    assert Permission.MONITORING_RUN not in permissions_for_role(officer.role)
    assert admin.role == UserRole.SYSTEM_ADMIN.value


def test_acknowledged_alert_remains_acknowledged_across_runs_and_scope_isolation(api_client, db_session):
    reference = datetime(2026, 11, 1, 12, tzinfo=ZoneInfo("Asia/Kolkata"))
    a, b = add_institution(db_session, code="MON-A"), add_institution(db_session, code="MON-B")
    record_a = add_fdr(db_session, a, maturity_date=reference.date() + timedelta(days=4))
    record_b = add_fdr(db_session, b)
    admin_a = add_user(db_session, UserRole.INSTITUTION_ADMIN.value, a.id)
    officer = add_user(db_session, UserRole.VERIFICATION_OFFICER.value)
    evaluate_maturities(db_session, reference_datetime=reference)
    alert_a = db_session.scalar(select(Alert).where(Alert.fdr_record_id == record_a.id, Alert.source == "system_rule"))
    ack = api_client.post(f"/api/v1/alerts/{alert_a.id}/acknowledge", headers=auth(officer))
    assert ack.status_code == 200 and ack.json()["status"] == "acknowledged"
    assert db_session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "alert_acknowledged")) == 1
    evaluate_maturities(db_session, reference_datetime=reference)
    assert db_session.scalar(select(Alert).where(Alert.id == alert_a.id)).status == "acknowledged"
    assert api_client.get(f"/api/v1/alerts/{alert_a.id}", headers=auth(admin_a)).status_code == 200
    alert_b = Alert(fdr_record_id=record_b.id, alert_type="manual_demo", severity="low", explanation="Synthetic", status="open", source="legacy_seed")
    db_session.add(alert_b); db_session.flush()
    assert api_client.get(f"/api/v1/alerts/{alert_b.id}", headers=auth(admin_a)).status_code == 404
    rows = api_client.get("/api/v1/alerts", headers=auth(admin_a)).json()
    assert all(item["fdr"]["institution_id"] == str(a.id) for item in rows["items"])


def test_alert_listing_filters_safe_details_and_monitoring_summary_agree(api_client, db_session):
    reference = datetime(2026, 11, 1, 12, tzinfo=ZoneInfo("Asia/Kolkata"))
    institution = add_institution(db_session)
    record = add_fdr(db_session, institution, maturity_date=reference.date() + timedelta(days=3))
    system = add_user(db_session, UserRole.SYSTEM_ADMIN.value)
    evaluate_maturities(db_session, reference_datetime=reference)
    detail = api_client.get("/api/v1/alerts", headers=auth(system)).json()["items"]
    owned = next(row for row in detail if row["fdr"]["internal_fdr_id"] == record.internal_fdr_id)
    full = api_client.get(f"/api/v1/alerts/{owned['id']}", headers=auth(system)).json()
    assert "password_hash" not in full and "actor_id" not in full and "fdr_record_id" not in full
    assert full["details"]["days_remaining"] == 3
    assert api_client.get(f"/api/v1/alerts?severity=high&rule_key=maturity_urgent&q={record.internal_fdr_id}", headers=auth(system)).json()["total"] == 1
    summary = api_client.get("/api/v1/monitoring/summary", headers=auth(system)).json()
    dashboard = api_client.get("/api/v1/dashboard/summary", headers=auth(system)).json()
    assert summary["counts_by_status"]["open"] == dashboard["unresolved_alerts"]
    assert sum(summary["upcoming_maturities_by_band"].get(key, 0) for key in ("maturity_urgent", "maturity_attention_required", "maturity_upcoming")) == dashboard["upcoming_maturities"]
    assert api_client.get("/api/v1/alerts?page=0", headers=auth(system)).status_code == 422
    assert api_client.get("/api/v1/alerts?sort_by=secret", headers=auth(system)).status_code == 422


def test_alert_permissions_and_no_delete_routes(api_client, db_session):
    institution = add_institution(db_session)
    admin = add_user(db_session, UserRole.SYSTEM_ADMIN.value)
    valid_rules = api_client.get("/api/v1/monitoring/rules", headers=auth(admin)).json()["items"]
    for role in UserRole:
        user = add_user(db_session, role.value, institution.id if role == UserRole.INSTITUTION_ADMIN else None)
        expected = 200 if Permission.ALERT_READ in permissions_for_role(role.value) else 403
        assert api_client.get("/api/v1/alerts", headers=auth(user)).status_code == expected
        assert api_client.get("/api/v1/monitoring/summary", headers=auth(user)).status_code == expected
        assert api_client.get("/api/v1/monitoring/rules", headers=auth(user)).status_code == expected
        run_expected = 200 if Permission.MONITORING_RUN in permissions_for_role(role.value) else 403
        assert api_client.get("/api/v1/monitoring/runs", headers=auth(user)).status_code == run_expected
        assert api_client.post("/api/v1/monitoring/run", json={}, headers=auth(user)).status_code == run_expected
        config_expected = 200 if Permission.MONITORING_CONFIGURE in permissions_for_role(role.value) else 403
        assert api_client.put("/api/v1/monitoring/rules", json=valid_rules, headers=auth(user)).status_code == config_expected
        record = add_fdr(db_session, institution)
        alert = Alert(fdr_record_id=record.id, alert_type=f"matrix_{role.value}", severity="low", explanation="Synthetic", status="open", source="legacy_seed")
        db_session.add(alert); db_session.flush()
        assert api_client.get(f"/api/v1/alerts/{alert.id}", headers=auth(user)).status_code == expected
        manage_expected = 200 if Permission.ALERT_MANAGE in permissions_for_role(role.value) else 403
        assert api_client.post(f"/api/v1/alerts/{alert.id}/acknowledge", headers=auth(user)).status_code == manage_expected
        if manage_expected == 200:
            assert api_client.post(f"/api/v1/alerts/{alert.id}/resolve", json={"remarks":"Synthetic test"}, headers=auth(user)).status_code == 200
        else:
            assert api_client.post(f"/api/v1/alerts/{alert.id}/resolve", json={"remarks":"Synthetic test"}, headers=auth(user)).status_code == 403
    all_routes = __import__("app.main", fromlist=["app"]).app.routes
    assert not any("DELETE" in getattr(route, "methods", set()) for route in all_routes)


def test_rule_update_validation_and_audit(api_client, db_session):
    admin = add_user(db_session, UserRole.SYSTEM_ADMIN.value)
    response = api_client.get("/api/v1/monitoring/rules", headers=auth(admin))
    assert response.status_code == 200 and "not verified AICTE policy" in response.json()["demo_default_notice"]
    rules = response.json()["items"]
    invalid = [dict(rule, min_days=10) if rule["rule_key"] == "maturity_attention_required" else rule for rule in rules]
    assert api_client.put("/api/v1/monitoring/rules", json=invalid, headers=auth(admin)).status_code == 422
    assert api_client.put("/api/v1/monitoring/rules", json=rules, headers=auth(admin)).status_code == 200
    assert db_session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "maturity_rules_updated")) == 1


def test_record_failure_isolated_and_job_audit_is_summary_only(db_session, monkeypatch):
    import app.services.monitoring as service
    reference = datetime(2026, 11, 1, 12, tzinfo=ZoneInfo("Asia/Kolkata"))
    institution = add_institution(db_session)
    bad = add_fdr(db_session, institution, internal_fdr_id="MON-BAD", maturity_date=reference.date() + timedelta(days=3))
    good = add_fdr(db_session, institution, internal_fdr_id="MON-GOOD", maturity_date=reference.date() + timedelta(days=4))
    original = service._evaluate_record
    def faulty(session, record, *args):
        if record.id == bad.id:
            raise RuntimeError("synthetic test failure")
        return original(session, record, *args)
    monkeypatch.setattr(service, "_evaluate_record", faulty)
    run = service.evaluate_maturities(db_session, reference_datetime=reference)
    assert run.status == "partial_failure" and run.records_evaluated == 1
    assert run.errors_summary["errors"][0]["record_id"] == str(bad.id)
    assert db_session.scalar(select(Alert).where(Alert.fdr_record_id == good.id, Alert.status == "open"))
    event = db_session.scalar(select(AuditEvent).where(AuditEvent.action == "monitoring_run_completed"))
    assert event and "record_id" not in event.change_summary


def test_scheduler_job_configuration_and_alert_unique_index(db_session, monkeypatch):
    from app.services.scheduler import build_scheduler
    monkeypatch.setenv("MONITORING_RUN_HOUR", "3")
    monkeypatch.setenv("MONITORING_RUN_MINUTE", "15")
    scheduler = build_scheduler()
    assert len(scheduler.get_jobs()) == 1
    institution = add_institution(db_session)
    record = add_fdr(db_session, institution)
    db_session.add(Alert(fdr_record_id=record.id, alert_type="test_unique", severity="low", explanation="x", status="open"))
    db_session.flush()
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(Alert(fdr_record_id=record.id, alert_type="test_unique", severity="low", explanation="x", status="open"))
            db_session.flush()


def test_advisory_lock_skips_concurrent_run_and_scheduler_enable_switch(db_engine, monkeypatch):
    from sqlalchemy.orm import Session
    import app.services.monitoring as service
    import app.services.scheduler as scheduler_module

    with Session(db_engine) as setup:
        institution = add_institution(setup)
        add_fdr(setup, institution)
        setup.commit()
    locked = Event()
    release = Event()
    original = service._evaluate_record
    def pause_inside_record(*args, **kwargs):
        locked.set()
        assert release.wait(5)
        return original(*args, **kwargs)
    monkeypatch.setattr(service, "_evaluate_record", pause_inside_record)
    result_holder = []
    def first_run():
        with Session(db_engine) as session:
            result_holder.append(service.evaluate_maturities(session, trigger="manual"))
    worker = Thread(target=first_run)
    worker.start()
    assert locked.wait(5)
    with Session(db_engine) as second:
        skipped = service.evaluate_maturities(second, trigger="manual")
    release.set(); worker.join(5)
    assert not worker.is_alive()
    assert skipped.status == "skipped_locked"
    assert result_holder[0].status == "success"

    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    assert scheduler_module.optional_scheduler() is None
    monkeypatch.setattr(scheduler_module, "scheduler_enabled", lambda: True)
    enabled = scheduler_module.optional_scheduler()
    assert enabled is not None and len(enabled.get_jobs()) == 1
    assert __import__("os").environ["SCHEDULER_ENABLED"] == "false"


def test_matured_or_closed_records_auto_resolve_owned_alerts(db_session):
    reference = datetime(2026, 11, 1, 12, tzinfo=ZoneInfo("Asia/Kolkata"))
    institution = add_institution(db_session)
    record = add_fdr(db_session, institution, maturity_date=reference.date() + timedelta(days=2))
    evaluate_maturities(db_session, reference_datetime=reference)
    record.record_status = "matured"
    resolved = evaluate_maturities(db_session, reference_datetime=reference)
    assert resolved.alerts_resolved == 1
    owned = db_session.scalar(select(Alert).where(Alert.fdr_record_id == record.id, Alert.source == "system_rule"))
    assert owned.status == "resolved" and owned.resolution_type == "auto"


def test_timezone_edge_uses_next_date_in_configured_zone(db_session):
    utc_reference = datetime(2026, 11, 1, 18, 30, tzinfo=ZoneInfo("UTC"))
    institution = add_institution(db_session)
    record = add_fdr(db_session, institution, maturity_date=date(2026, 11, 3))
    evaluate_maturities(db_session, reference_datetime=utc_reference)
    alert = db_session.scalar(select(Alert).where(Alert.fdr_record_id == record.id, Alert.source == "system_rule"))
    assert alert.details["reference_date"] == "2026-11-02"
    assert alert.details["days_remaining"] == 1


def test_seeded_alerts_are_preserved_and_legacy_maturity_row_is_adopted(db_session):
    from app.seed import seed_synthetic_data
    from app.models.enums import AlertStatus

    ref = date(2026, 11, 1)
    db_session.execute(delete(Alert))
    db_session.flush()
    seed_synthetic_data(db_session, reference_date=ref)
    seeded = db_session.scalars(select(Alert)).all()
    assert len(seeded) == 7
    owner = next(alert for alert in seeded if alert.alert_type == "maturity_upcoming")
    assert owner.source == "system_rule" and owner.rule_key == "maturity_upcoming"
    assert sum(alert.source == "legacy_seed" for alert in seeded) == 6
    run = evaluate_maturities(db_session, reference_datetime=datetime(2026, 11, 1, 12, tzinfo=ZoneInfo("Asia/Kolkata")))
    assert run.status == "success"
    assert db_session.scalar(select(func.count()).select_from(Alert).where(Alert.fdr_record_id == owner.fdr_record_id,
        Alert.status.in_([AlertStatus.OPEN.value, AlertStatus.ACKNOWLEDGED.value]))) == 1
