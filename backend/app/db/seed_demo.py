"""One-off production command to seed synthetic data and set demo passwords."""

import os

from sqlalchemy.orm import Session

from app.core.config import app_environment, database_url, validate_security_settings
from app.db.confirmation import confirm_database_write
from app.db.demo_passwords import update_synthetic_user_passwords
from app.db.session import make_engine
from app.seed import seed_synthetic_data


def main() -> None:
    if app_environment() not in {"development", "production"}:
        raise SystemExit("seed_demo requires APP_ENV=development or production")
    validate_security_settings()
    password = os.getenv("SEED_DEMO_PASSWORD")
    if not password:
        raise SystemExit("SEED_DEMO_PASSWORD must be set for the one-off demo seed")
    url = database_url()
    if not url:
        raise SystemExit("DATABASE_URL must be configured")
    confirm_database_write(url, action="seed", expected="SEED")
    engine = make_engine(url)
    try:
        with Session(engine) as session, session.begin():
            counts = seed_synthetic_data(session)
            user_count = update_synthetic_user_passwords(session, password)
        print(f"Synthetic demo seed completed: {counts}; demo passwords set for {user_count} synthetic users.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
