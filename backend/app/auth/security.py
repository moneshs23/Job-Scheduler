import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum

import bcrypt
from jose import JWTError, jwt

from app.config.settings import get_settings

settings = get_settings()

BCRYPT_MAX_BYTES = 72


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


def hash_password(password: str) -> str:
    truncated = password.encode("utf-8")[:BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(truncated, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    truncated = plain_password.encode("utf-8")[:BCRYPT_MAX_BYTES]
    return bcrypt.checkpw(truncated, password_hash.encode("utf-8"))


def _create_token(subject: str, token_type: TokenType, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type.value,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: uuid.UUID) -> str:
    return _create_token(
        str(user_id), TokenType.ACCESS, timedelta(minutes=settings.access_token_expire_minutes)
    )


def create_refresh_token(user_id: uuid.UUID) -> str:
    return _create_token(
        str(user_id), TokenType.REFRESH, timedelta(days=settings.refresh_token_expire_days)
    )


def decode_token(token: str, expected_type: TokenType) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc

    if payload.get("type") != expected_type.value:
        raise ValueError(f"Expected a {expected_type.value} token")

    subject = payload.get("sub")
    if subject is None:
        raise ValueError("Token missing subject")

    return uuid.UUID(subject)


def generate_api_key() -> tuple[str, str, str]:
    """Returns (full_key, key_prefix, key_hash) — only the full key is ever shown to the user."""
    raw = secrets.token_urlsafe(32)
    prefix = raw[:8]
    full_key = f"djs_{raw}"
    key_hash = hash_api_key(full_key)
    return full_key, prefix, key_hash


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
