"""Optional in-process daily scheduler for maturity evaluation."""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import app_timezone, monitoring_run_time, scheduler_enabled


def scheduled_run() -> None:
    from app.db.session import make_session_factory
    from app.services.monitoring import evaluate_maturities

    session = make_session_factory()()
    try:
        evaluate_maturities(session, trigger="scheduled")
    finally:
        session.close()


def build_scheduler() -> BackgroundScheduler:
    tz = app_timezone()
    hour, minute = monitoring_run_time()
    scheduler = BackgroundScheduler(timezone=tz)
    scheduler.add_job(scheduled_run, trigger=CronTrigger(hour=hour, minute=minute, timezone=tz),
        id="maturity-monitoring-daily", name="Daily maturity monitoring", replace_existing=True,
        max_instances=1, coalesce=True, misfire_grace_time=3600)
    return scheduler


def optional_scheduler() -> BackgroundScheduler | None:
    return build_scheduler() if scheduler_enabled() else None
