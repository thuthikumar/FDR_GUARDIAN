"""SQLAlchemy engine and session factory."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import database_url


def make_engine(url: str | None = None):
    resolved_url = url or database_url()
    if not resolved_url:
        raise RuntimeError("DATABASE_URL is not configured")
    return create_engine(resolved_url, pool_pre_ping=True)


def make_session_factory(url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=make_engine(url), expire_on_commit=False)


@lru_cache(maxsize=1)
def _default_session_factory() -> sessionmaker[Session]:
    return make_session_factory()


def get_session() -> Generator[Session, None, None]:
    """FastAPI-ready session dependency for later phases."""
    session = _default_session_factory()()
    try:
        yield session
    finally:
        session.close()
