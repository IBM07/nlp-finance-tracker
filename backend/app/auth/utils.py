# ==========================================
# auth/utils.py — Password Hashing & JWT
# ==========================================
# Implements:
#   hash_password(plain)         → bcrypt hash string
#   verify_password(plain, hash) → bool
#   create_access_token(data)    → signed JWT string (short-lived)
#   create_refresh_token(data)   → signed JWT string (long-lived, 7 days)
#   decode_token(token)          → payload dict (raises on expired/invalid)
#
# Design decisions:
#   - bcrypt (direct): passlib is abandoned and incompatible with bcrypt >= 4.x.
#     We call bcrypt directly — same algorithm, same cost factor (12), same wire
#     format ($2b$...) — just without the broken wrapper.
#   - python-jose for JWT: handles HS256 signing, expiry, and claim validation.
#   - Separate access (15 min) and refresh (7 days) tokens.
#     Access tokens are short so a leaked token expires quickly.
#     Refresh tokens are long-lived but stored server-side and can be revoked.
# ==========================================

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()

# ---------------------------------------------------------------------------
# Password Hashing
# ---------------------------------------------------------------------------

# bcrypt work factor — 12 is the widely accepted production default.
# Higher = slower to brute-force; each increment doubles the compute time.
_BCRYPT_ROUNDS = 12


def hash_password(plain: str) -> str:
    """Returns the bcrypt hash of a plain-text password (encoded as $2b$...)."""
    return bcrypt.hashpw(
        plain.encode("utf-8"),
        bcrypt.gensalt(rounds=_BCRYPT_ROUNDS),
    ).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """
    Returns True if *plain* matches the stored *hashed* password.
    Uses bcrypt's built-in constant-time comparison — safe against timing attacks.
    """
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ---------------------------------------------------------------------------
# Token constants
# ---------------------------------------------------------------------------

# Access token: short-lived, stateless (no server-side storage needed)
ACCESS_TOKEN_TYPE = "access"

# Refresh token: long-lived, but we validate it against a server-side set
# of valid refresh token IDs (stored in memory for now; swap to Redis/DB later)
REFRESH_TOKEN_TYPE = "refresh"
REFRESH_TOKEN_EXPIRE_DAYS = 7


# ---------------------------------------------------------------------------
# JWT Creation
# ---------------------------------------------------------------------------

def _create_token(data: dict, token_type: str, expires_delta: timedelta) -> str:
    """
    Internal helper: creates a signed JWT with an expiry claim.

    Args:
        data:          Claims to include (e.g. {"sub": "42"}).
        token_type:    "access" or "refresh" — stored in the "type" claim.
        expires_delta: How long until the token expires.

    Returns:
        Signed JWT string.
    """
    payload = data.copy()
    expire = datetime.now(tz=timezone.utc) + expires_delta
    payload.update({"exp": expire, "type": token_type})
    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def create_access_token(data: dict) -> str:
    """
    Creates a short-lived access token.
    data MUST contain {"sub": str(user_id)}.
    """
    return _create_token(
        data=data,
        token_type=ACCESS_TOKEN_TYPE,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(data: dict) -> str:
    """
    Creates a long-lived refresh token (7 days).
    data MUST contain {"sub": str(user_id)}.
    The caller is responsible for persisting the token's "jti" claim
    server-side if revocation is needed (see auth/routes.py logout logic).
    """
    import secrets
    payload = data.copy()
    payload["jti"] = secrets.token_hex(16)   # unique token ID for revocation
    return _create_token(
        data=payload,
        token_type=REFRESH_TOKEN_TYPE,
        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )


# ---------------------------------------------------------------------------
# JWT Decoding
# ---------------------------------------------------------------------------

def decode_token(token: str) -> dict:
    """
    Decodes and validates a JWT.

    Raises:
        jose.JWTError — if the token is expired, tampered with, or malformed.

    Returns:
        The decoded payload dict.
    """
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )


def decode_access_token(token: str) -> dict:
    """
    Decodes a JWT and asserts it is an access token.

    Raises:
        JWTError — if the token is invalid or is not an access token.
    """
    payload = decode_token(token)
    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise JWTError("Token type mismatch: expected access token.")
    return payload


def decode_refresh_token(token: str) -> dict:
    """
    Decodes a JWT and asserts it is a refresh token.

    Raises:
        JWTError — if the token is invalid or is not a refresh token.
    """
    payload = decode_token(token)
    if payload.get("type") != REFRESH_TOKEN_TYPE:
        raise JWTError("Token type mismatch: expected refresh token.")
    return payload
