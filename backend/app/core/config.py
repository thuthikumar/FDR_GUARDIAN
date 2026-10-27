"""Environment-backed configuration."""

import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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


def maturity_thresholds() -> tuple[int, int, int]:
    """Return demo cutoffs as (urgent, attention, upcoming) days."""
    try:
        urgent = int(os.getenv("MATURITY_URGENT_DAYS", "7"))
        attention = int(os.getenv("MATURITY_ATTENTION_DAYS", "30"))
        upcoming = int(os.getenv("MATURITY_UPCOMING_DAYS", "90"))
    except ValueError as exc:
        raise RuntimeError("Maturity demo thresholds must be positive integers") from exc
    if not (0 < urgent < attention < upcoming):
        raise RuntimeError("Maturity demo thresholds must satisfy 0 < urgent < attention < upcoming")
    return urgent, attention, upcoming


def app_timezone() -> ZoneInfo:
    name = os.getenv("APP_TIMEZONE", "Asia/Kolkata").strip()
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError("APP_TIMEZONE must be a valid IANA timezone") from exc


def scheduler_enabled() -> bool:
    raw = os.getenv("SCHEDULER_ENABLED", "false").strip().lower()
    if raw not in {"true", "false"}:
        raise RuntimeError("SCHEDULER_ENABLED must be true or false")
    return raw == "true"


def monitoring_run_time() -> tuple[int, int]:
    try:
        hour = int(os.getenv("MONITORING_RUN_HOUR", "2"))
        minute = int(os.getenv("MONITORING_RUN_MINUTE", "0"))
    except ValueError as exc:
        raise RuntimeError("Monitoring run time must be numeric") from exc
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise RuntimeError("MONITORING_RUN_HOUR must be 0-23 and MONITORING_RUN_MINUTE 0-59")
    return hour, minute


def storage_root() -> Path:
    configured = os.getenv("STORAGE_ROOT", "").strip()
    return Path(configured).expanduser().resolve() if configured else (Path(__file__).resolve().parents[2] / "storage").resolve()


def validate_storage_root() -> Path:
    """Create private storage at startup and fail clearly when it is not writable."""
    root = storage_root()
    try:
        root.mkdir(parents=True, exist_ok=True)
        descriptor, probe_name = tempfile.mkstemp(prefix=".write-check-", dir=root)
        os.close(descriptor)
        Path(probe_name).unlink(missing_ok=True)
        try:
            root.chmod(0o700)
        except OSError:
            pass
    except OSError as exc:
        raise RuntimeError("STORAGE_ROOT must be a directory the application can create and write") from exc
    return root


def max_upload_bytes() -> int:
    return _positive_int("MAX_UPLOAD_MB", 10) * 1024 * 1024


def max_pdf_pages() -> int:
    return _positive_int("MAX_PDF_PAGES", 10)


def max_documents_per_fdr() -> int:
    return _positive_int("MAX_DOCUMENTS_PER_FDR", 20)


def ocr_enabled() -> bool:
    raw = os.getenv("OCR_ENABLED", "true").strip().lower()
    if raw not in {"true", "false"}:
        raise RuntimeError("OCR_ENABLED must be true or false")
    return raw == "true"


def tesseract_command() -> str | None:
    value = os.getenv("TESSERACT_CMD", "").strip()
    return value or None


def ocr_languages() -> str:
    value = os.getenv("OCR_LANGUAGES", "eng").strip()
    if not value or len(value) > 80 or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_+-" for ch in value):
        raise RuntimeError("OCR_LANGUAGES must be a valid language code list")
    return value


def ocr_timeout_seconds() -> int:
    return _positive_int("OCR_TIMEOUT_SECONDS", 60)


def processing_stale_minutes() -> int:
    return _positive_int("PROCESSING_STALE_MINUTES", 15)


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
