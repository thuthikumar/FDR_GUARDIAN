"""Environment-backed configuration."""

import os
from pathlib import Path
from urllib.parse import urlsplit

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
        return validate_test_database_url(make_url(configured))

    development_url = database_url()
    if not development_url:
        raise RuntimeError("Set DATABASE_URL or TEST_DATABASE_URL before running database tests")
    dev_url = make_url(development_url)
    if not dev_url.database:
        raise RuntimeError("DATABASE_URL must include a database name to derive the test database")
    return validate_test_database_url(dev_url.set(database=f"{dev_url.database}_test"))


def validate_test_database_url(test_url: URL) -> URL:
    """Refuse any test database that is not clearly isolated by its name."""
    if not test_url.database or not test_url.database.endswith("_test"):
        raise RuntimeError("Test database name must end with _test; refusing database setup or cleanup")
    development_url = database_url()
    if development_url and test_url.database == make_url(development_url).database:
        raise RuntimeError("Test database must differ from DATABASE_URL; refusing database setup or cleanup")
    return test_url


def jwt_secret_key() -> str:
    """Load the signing secret without supplying an insecure application default."""
    value = os.getenv("JWT_SECRET_KEY", "").strip()
    if len(value) < 32 or any(marker in value.lower() for marker in ("replace", "placeholder", "change-me", "your-secret")):
        raise RuntimeError("JWT_SECRET_KEY is required and must contain at least 32 characters")
    return value


def access_token_expire_minutes() -> int:
    return _positive_int("ACCESS_TOKEN_EXPIRE_MINUTES", 15)


def refresh_token_expire_days() -> int:
    return _positive_int("REFRESH_TOKEN_EXPIRE_DAYS", 7)


def refresh_token_reuse_grace_seconds() -> int:
    """Allow benign concurrent use of a just-rotated refresh token briefly."""
    raw = os.getenv("REFRESH_TOKEN_REUSE_GRACE_SECONDS", "10").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError("REFRESH_TOKEN_REUSE_GRACE_SECONDS must be a non-negative integer") from exc
    if value < 0:
        raise RuntimeError("REFRESH_TOKEN_REUSE_GRACE_SECONDS must be a non-negative integer")
    return value


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be a positive integer")
    return value


def app_environment() -> str:
    return os.getenv("APP_ENV", "development").strip().lower()


def cookie_secure() -> bool:
    raw = os.getenv("COOKIE_SECURE", "false").strip().lower()
    if raw not in {"true", "false"}:
        raise RuntimeError("COOKIE_SECURE must be true or false")
    secure = raw == "true"
    if app_environment() == "production" and not secure:
        raise RuntimeError("COOKIE_SECURE must be true when APP_ENV=production")
    return secure


def frontend_origin() -> str:
    origin = os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5173").strip().rstrip("/")
    parsed = urlsplit(origin)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path or parsed.query or parsed.fragment:
        raise RuntimeError("FRONTEND_ORIGIN must be an http or https origin")
    return origin


def validate_security_settings() -> None:
    """Fail application startup when auth secrets or production cookie policy are unsafe."""
    jwt_secret_key()
    access_token_expire_minutes()
    refresh_token_expire_days()
    cookie_secure()
    frontend_origin()
