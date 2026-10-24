"""
Login tokens.

- Access token: a signed JWT the app sends with every request
  ("Authorization: Bearer …"). Short-lived.
- Refresh token: a long random string the app swaps for a new pair of tokens
  when the access token expires. Stored only as a hash, deleted on log out,
  and replaced every time it's used (so a stolen old one stops working).
"""

import hashlib
import secrets
import uuid
from datetime import timedelta

import jwt
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import RefreshToken, utcnow

ALGORITHM = "HS256"


def create_access_token(user_id: uuid.UUID) -> str:
    s = get_settings()
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=s.access_token_minutes),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=ALGORITHM)


def read_access_token(token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        return None


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_refresh_token(db: Session, user_id: uuid.UUID) -> str:
    token = secrets.token_urlsafe(48)
    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=_hash(token),
            expires_at=utcnow() + timedelta(days=get_settings().refresh_token_days),
        )
    )
    return token


def use_refresh_token(db: Session, token: str) -> uuid.UUID | None:
    """Consume a refresh token. Returns its user, or None if invalid/expired."""
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash(token)))
    if row is None:
        return None
    db.delete(row)
    if row.expires_at < utcnow():
        return None
    return row.user_id


def revoke_refresh_token(db: Session, token: str) -> None:
    db.execute(delete(RefreshToken).where(RefreshToken.token_hash == _hash(token)))
