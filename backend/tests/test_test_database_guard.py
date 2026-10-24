from sqlalchemy.engine import make_url
import pytest

from app.core import config


def test_test_database_url_requires_test_suffix(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/dev_db")
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+psycopg://user:pass@localhost/other_db")

    try:
        config.test_database_url()
    except RuntimeError as exc:
        assert "must end with _test" in str(exc)
    else:
        raise AssertionError("non-test database name was accepted")


def test_test_database_url_rejects_dev_database_before_fixture_setup(monkeypatch) -> None:
    dev_url = make_url("postgresql+psycopg://user:pass@localhost/shared_test")
    monkeypatch.setenv("DATABASE_URL", str(dev_url))
    monkeypatch.setenv("TEST_DATABASE_URL", str(dev_url))

    try:
        config.test_database_url()
    except RuntimeError as exc:
        assert "must differ" in str(exc)
    else:
        raise AssertionError("development database was accepted for tests")


def test_database_fixture_refuses_non_test_name_before_setup_or_cleanup(monkeypatch) -> None:
    import conftest

    unsafe_url = make_url("postgresql+psycopg://user:pass@localhost/development_db")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/development_db")
    monkeypatch.setattr(conftest, "test_database_url", lambda: unsafe_url)
    monkeypatch.setattr(conftest, "_ensure_test_database", lambda *_: pytest.fail("database setup ran before validation"))
    monkeypatch.setattr(conftest.command, "upgrade", lambda *_: pytest.fail("migration ran before validation"))
    fixture_generator = conftest.migrated_test_database.__wrapped__()

    with pytest.raises(RuntimeError, match="must end with _test"):
        next(fixture_generator)
