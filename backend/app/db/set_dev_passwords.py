"""Set local demo passwords for synthetic users only."""

import os
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import app_environment, database_url
from app.core.security import hash_password
from app.db.session import make_engine
from app.models.users import User


def run_set_dev_passwords(session: Session, password: str | None, environment: str) -> int:
    if environment.strip().lower() == "production":
        raise RuntimeError("set_dev_passwords is disabled when APP_ENV=production")
    if not password:
        raise RuntimeError("SEED_DEV_PASSWORD is for local development passwords and must be set")
    if len(password) < 12 or password.strip().lower().startswith("replace-"):
        raise RuntimeError("SEED_DEV_PASSWORD must contain at least 12 characters")

    users = session.scalars(select(User).where(User.is_synthetic.is_(True))).all()
    now = datetime.now(timezone.utc)
    for user in users:
        user.password_hash = hash_password(password)
        user.password_changed_at = now
    session.commit()
    return len(users)


def main() -> None:
    environment = app_environment()
    password = os.getenv("SEED_DEV_PASSWORD")
    # Refuse before opening a database connection in production or without a password.
    if environment == "production":
        raise SystemExit("set_dev_passwords is disabled when APP_ENV=production")
    if not password:
        raise SystemExit("SEED_DEV_PASSWORD is for local development passwords and must be set")
    if len(password) < 12 or password.strip().lower().startswith("replace-"):
        raise SystemExit("SEED_DEV_PASSWORD must contain at least 12 non-placeholder characters")
    url = database_url()
    if not url:
        raise SystemExit("DATABASE_URL must be configured")
    engine = make_engine(url)
    try:
        with Session(engine) as session:
            count = run_set_dev_passwords(session, password, environment)
        print(f"Updated passwords for {count} synthetic users.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
