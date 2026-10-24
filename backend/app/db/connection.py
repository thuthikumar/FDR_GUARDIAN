"""PostgreSQL connectivity check."""

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import database_url


def check_database() -> dict[str, str]:
    """Try a lightweight query and return a safe status for the API client."""
    url = database_url()
    if not url:
        return {"status": "not_configured"}

    try:
        engine = create_engine(url, pool_pre_ping=True)
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        finally:
            engine.dispose()
    except (SQLAlchemyError, ValueError):
        return {"status": "unavailable"}

    return {"status": "connected"}
