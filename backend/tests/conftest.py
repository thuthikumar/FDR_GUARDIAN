"""Dedicated PostgreSQL test database setup; never points at the dev database."""

from collections.abc import Generator
from pathlib import Path
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.core.config import test_database_url, validate_test_database_url

# A test-only signing key keeps imports deterministic; production has no default.
os.environ.setdefault("JWT_SECRET_KEY", "test-only-signing-key-not-for-use-outside-tests")


BACKEND_DIR = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
    "users",
    "refresh_tokens",
    "institutions",
    "fdr_records",
    "documents",
    "extracted_fields",
    "verification_cases",
    "approval_actions",
    "release_events",
    "alerts",
    "notifications",
    "audit_events",
    "integration_sync_runs",
}


def _alembic_config(url: URL) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%"))
    return config


def _ensure_test_database(url: URL) -> None:
    if not url.database:
        raise RuntimeError("TEST_DATABASE_URL must include a database name")
    admin_url = url.set(database="postgres")
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
            )
            if not exists:
                identifier = engine.dialect.identifier_preparer.quote(url.database)
                connection.exec_driver_sql(f"CREATE DATABASE {identifier}")
    finally:
        engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def migrated_test_database() -> Generator[URL, None, None]:
    """Create/migrate and clear only the explicitly separate test database."""
    # Keep this assertion immediately before all database creation/migration/truncation.
    url = validate_test_database_url(test_database_url())
    _ensure_test_database(url)
    command.upgrade(_alembic_config(url), "head")

    engine = create_engine(url)
    try:
        from app.db.base import Base
        import app.models  # noqa: F401

        table_names = [table.name for table in Base.metadata.sorted_tables]
        quoted = ", ".join(engine.dialect.identifier_preparer.quote(name) for name in table_names)
        if quoted:
            with engine.begin() as connection:
                connection.exec_driver_sql(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE")
        yield url
    finally:
        engine.dispose()


@pytest.fixture
def db_engine(migrated_test_database: URL):
    engine = create_engine(migrated_test_database)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(db_engine) -> Generator[Session, None, None]:
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()
