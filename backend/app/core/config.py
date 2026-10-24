"""Environment-backed configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL, make_url


# Load the project-level .env for local development; existing process variables win.
load_dotenv(Path(__file__).resolve().parents[3] / ".env")


def database_url() -> str | None:
    """Return the database URL, if configured."""
    value = os.getenv("DATABASE_URL", "").strip()
    return value or None


def test_database_url() -> URL:
    """Return an explicitly configured or safely derived, separate test DB URL."""
    configured = os.getenv("TEST_DATABASE_URL", "").strip()
    if configured:
        test_url = make_url(configured)
        development_url = database_url()
        if development_url and test_url.database == make_url(development_url).database:
            raise RuntimeError("TEST_DATABASE_URL must point to a database separate from DATABASE_URL")
        return test_url

    development_url = database_url()
    if not development_url:
        raise RuntimeError("Set DATABASE_URL or TEST_DATABASE_URL before running database tests")
    dev_url = make_url(development_url)
    if not dev_url.database:
        raise RuntimeError("DATABASE_URL must include a database name to derive the test database")
    return dev_url.set(database=f"{dev_url.database}_test")
