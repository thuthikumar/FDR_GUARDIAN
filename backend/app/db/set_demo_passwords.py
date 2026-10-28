"""One-off production command to rotate passwords for synthetic demo users."""

import os

from sqlalchemy.orm import Session

from app.core.config import app_environment, database_url, validate_security_settings
from app.db.demo_passwords import update_synthetic_user_passwords
from app.db.session import make_engine


def main() -> None:
    if app_environment() != "production":
        raise SystemExit("set_demo_passwords requires APP_ENV=production")
    validate_security_settings()
    password = os.getenv("SEED_DEMO_PASSWORD")
    if not password:
        raise SystemExit("SEED_DEMO_PASSWORD must be set")
    url = database_url()
    if not url:
        raise SystemExit("DATABASE_URL must be configured")
    engine = make_engine(url)
    try:
        with Session(engine) as session, session.begin():
            count = update_synthetic_user_passwords(session, password)
        print(f"Updated passwords for {count} synthetic users.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
