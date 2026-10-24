from sqlalchemy.engine import make_url

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
