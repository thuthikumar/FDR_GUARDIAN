from fastapi import Response
import pytest
from fastapi.testclient import TestClient
from app.core.config import app_environment, database_url, validate_database_settings, validate_security_settings
from app.db.confirmation import confirm_database_write
from app.core.security import verify_password
from app.db.demo_passwords import update_synthetic_user_passwords
from app.models.enums import UserRole
from app.models.users import User


def test_neon_postgres_url_uses_psycopg_and_preserves_sslmode(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@db.invalid/fdr_demo?sslmode=require")
    resolved = database_url()
    assert resolved is not None
    assert resolved.startswith("postgresql+psycopg://")
    assert "sslmode=require" in resolved


def test_production_database_url_is_required_and_placeholders_are_rejected(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    try:
        validate_database_settings()
    except RuntimeError as error:
        assert "DATABASE_URL" in str(error)
    else:
        raise AssertionError("production accepted a missing DATABASE_URL")

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@db.example.invalid/fdr")
    try:
        validate_database_settings()
    except RuntimeError as error:
        assert "DATABASE_URL" in str(error)
    else:
        raise AssertionError("production accepted a placeholder DATABASE_URL")

    monkeypatch.setenv("DATABASE_URL", "sqlite:///not-postgres.db")
    try:
        validate_database_settings()
    except RuntimeError as error:
        assert "PostgreSQL" in str(error)
    else:
        raise AssertionError("production accepted a non-PostgreSQL DATABASE_URL")


def test_production_app_disables_openapi_and_sets_secure_refresh_cookie(monkeypatch):
    from app.api.auth import _set_refresh_cookie
    from app.main import create_app

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@db.invalid/fdr_demo?sslmode=require")
    monkeypatch.setenv("JWT_SECRET_KEY", "a-production-signing-key-with-more-than-32-characters")
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://demo.example.invalid")
    monkeypatch.setenv("COOKIE_SECURE", "true")

    application = create_app()
    assert application.docs_url is None
    assert application.redoc_url is None
    assert application.openapi_url is None
    cors = next(middleware for middleware in application.user_middleware if middleware.cls.__name__ == "CORSMiddleware")
    assert cors.kwargs["allow_origins"] == ["https://demo.example.invalid"]

    response = Response()
    _set_refresh_cookie(response, "synthetic-test-token")
    cookie = response.headers["set-cookie"].lower()
    assert "secure" in cookie and "httponly" in cookie and "samesite=strict" in cookie


def test_demo_password_command_updates_only_synthetic_users(db_session):
    synthetic = User(
        email="synthetic-password@synthetic.invalid",
        full_name="Synthetic User",
        role=UserRole.SYSTEM_ADMIN.value,
        is_active=True,
        is_synthetic=True,
    )
    ordinary = User(
        email="ordinary-password@synthetic.invalid",
        full_name="Ordinary User",
        role=UserRole.SYSTEM_ADMIN.value,
        is_active=True,
        is_synthetic=False,
    )
    db_session.add_all([synthetic, ordinary])
    db_session.flush()

    assert update_synthetic_user_passwords(db_session, "synthetic-demo-password") == 1
    db_session.refresh(synthetic)
    db_session.refresh(ordinary)
    assert synthetic.password_hash is not None and verify_password(synthetic.password_hash, "synthetic-demo-password")
    assert ordinary.password_hash is None


@pytest.mark.parametrize("value", ["prod", "Production", "staging", ""])
def test_app_environment_rejects_values_outside_exact_allowlist(monkeypatch, value):
    monkeypatch.setenv("APP_ENV", value)
    with pytest.raises(RuntimeError, match="APP_ENV must be"):
        app_environment()


def _valid_production_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@db.invalid/fdr_demo?sslmode=require")
    monkeypatch.setenv("JWT_SECRET_KEY", "a-valid-production-signing-secret-of-32-chars")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://demo.invalid")


def test_production_security_configuration_accepts_valid_values(monkeypatch):
    _valid_production_environment(monkeypatch)
    validate_security_settings()


def test_production_security_configuration_rejects_each_required_setting(monkeypatch):
    _valid_production_environment(monkeypatch)
    monkeypatch.delenv("DATABASE_URL")
    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        validate_security_settings()

    _valid_production_environment(monkeypatch)
    monkeypatch.setenv("JWT_SECRET_KEY", "short")
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        validate_security_settings()

    _valid_production_environment(monkeypatch)
    monkeypatch.setenv("JWT_SECRET_KEY", "replace-with-a-real-secret-of-32-chars")
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        validate_security_settings()

    _valid_production_environment(monkeypatch)
    monkeypatch.setenv("COOKIE_SECURE", "false")
    with pytest.raises(RuntimeError, match="COOKIE_SECURE must be true"):
        validate_security_settings()

    _valid_production_environment(monkeypatch)
    monkeypatch.delenv("FRONTEND_ORIGIN")
    with pytest.raises(RuntimeError, match="FRONTEND_ORIGIN is required"):
        validate_security_settings()

    _valid_production_environment(monkeypatch)
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://demo.invalid")
    with pytest.raises(RuntimeError, match="FRONTEND_ORIGIN must be a public HTTPS origin"):
        validate_security_settings()


def test_production_docs_routes_return_404_and_health_returns_200(monkeypatch):
    _valid_production_environment(monkeypatch)
    from app.main import create_app

    client = TestClient(create_app())
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "service": "fdr-guardian-api"}


def test_database_url_warns_for_neon_pooler_host(monkeypatch, caplog):
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@db-pooler.invalid/fdr?sslmode=require")
    with caplog.at_level("WARNING", logger="fdr_guardian.config"):
        resolved = database_url()
    assert resolved.startswith("postgresql+psycopg://")
    assert "pooler" in caplog.text.lower()
    assert "advisory locks and Alembic" in caplog.text
    assert "secret" not in caplog.text


def test_startup_security_validation_warns_for_pooler_host_in_development(monkeypatch, caplog):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@db-pooler.invalid/fdr?sslmode=require")
    monkeypatch.setenv("JWT_SECRET_KEY", "a-local-test-signing-secret-with-more-than-32-chars")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://127.0.0.1:5173")
    with caplog.at_level("WARNING", logger="fdr_guardian.config"):
        validate_security_settings()
    assert "pooler" in caplog.text.lower()
    assert "advisory locks and Alembic" in caplog.text
    assert "secret" not in caplog.text


def test_process_environment_direct_neon_url_overrides_dotenv_in_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "postgresql://laptop:terminal-only@ep-direct.invalid/fdr_demo?sslmode=require")
    resolved = database_url()
    assert resolved.startswith("postgresql+psycopg://laptop:")
    assert "@ep-direct.invalid/fdr_demo" in resolved
    assert "sslmode=require" in resolved


@pytest.mark.parametrize("answer,continues", [("SEED", True), ("ROTATE", True), ("no", False)])
def test_demo_write_confirmation_shows_only_host(answer, continues, capsys):
    url = "postgresql://private-user:private-password@db.example.invalid/fdr_demo?sslmode=require"
    if continues:
        confirm_database_write(url, action="seed", expected=answer, input_fn=lambda _prompt: answer)
    else:
        with pytest.raises(SystemExit, match="no database changes were made"):
            confirm_database_write(url, action="seed", expected="SEED", input_fn=lambda _prompt: answer)
    output = capsys.readouterr().out
    assert "db.example.invalid" in output
    assert "private-user" not in output and "private-password" not in output


@pytest.mark.parametrize("module_name,confirmation", [
    ("app.db.seed_demo", "SEED"),
    ("app.db.set_demo_passwords", "ROTATE"),
])
def test_demo_cli_cancels_before_opening_database(monkeypatch, capsys, module_name, confirmation):
    import importlib

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "postgresql://laptop:private-password@direct.invalid/fdr_demo?sslmode=require")
    monkeypatch.setenv("JWT_SECRET_KEY", "a-local-test-signing-secret-with-more-than-32-chars")
    monkeypatch.setenv("SEED_DEMO_PASSWORD", "synthetic-demo-password")
    module = importlib.import_module(module_name)
    prompts = []
    monkeypatch.setattr("builtins.input", lambda prompt: prompts.append(prompt) or "cancel")
    monkeypatch.setattr(module, "make_engine", lambda _url: pytest.fail("engine must not be opened before confirmation"))
    with pytest.raises(SystemExit, match="no database changes were made"):
        module.main()
    output = capsys.readouterr().out
    assert "direct.invalid" in output
    assert "private-password" not in output and "laptop" not in output
    assert confirmation in prompts[0]
