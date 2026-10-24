"""Password hashing and short-lived access-token primitives."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import access_token_expire_minutes, jwt_secret_key


PASSWORD_HASHER = PasswordHasher(time_cost=2, memory_cost=19_456, parallelism=1)
_DUMMY_HASH = PASSWORD_HASHER.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Always do Argon2 work, using a process-local dummy hash for missing users/hashes."""
    candidate = password_hash or _DUMMY_HASH
    try:
        valid = PASSWORD_HASHER.verify(candidate, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        valid = False
    return bool(password_hash) and valid


def create_access_token(user_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=access_token_expire_minutes())
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": expires, "jti": secrets.token_urlsafe(12), "typ": "access"},
        jwt_secret_key(),
        algorithm="HS256",
    )


def decode_access_token(token: str) -> UUID:
    payload = jwt.decode(token, jwt_secret_key(), algorithms=["HS256"])
    if payload.get("typ") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    try:
        return UUID(payload["sub"])
    except (KeyError, ValueError, TypeError) as exc:
        raise jwt.InvalidTokenError("invalid subject") from exc


def create_refresh_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
