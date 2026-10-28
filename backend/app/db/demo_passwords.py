"""Set a password for synthetic demo users only."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.users import User


def validate_demo_password(password: str | None) -> str:
    if not password or len(password) < 12 or password.strip().lower().startswith("replace-"):
        raise RuntimeError("SEED_DEMO_PASSWORD must contain at least 12 non-placeholder characters")
    return password


def update_synthetic_user_passwords(session: Session, password: str | None) -> int:
    password = validate_demo_password(password)
    users = session.scalars(select(User).where(User.is_synthetic.is_(True))).all()
    if not users:
        raise RuntimeError("No synthetic demo users exist; seed synthetic data before setting passwords")
    now = datetime.now(timezone.utc)
    for user in users:
        user.password_hash = hash_password(password)
        user.password_changed_at = now
    session.flush()
    return len(users)
