# ==========================================
# auth/routes.py — Authentication Endpoints
# ==========================================
# Implements:
#   POST /auth/signup   — create a new account
#   POST /auth/login    — verify credentials, return access + refresh tokens
#   POST /auth/refresh  — exchange a valid refresh token for a new access token
#   POST /auth/logout   — invalidate the user's refresh token (server-side)
#   GET  /auth/me       — return current user info (requires access token)
#
# Refresh token strategy (in-memory, single-instance):
#   We keep a set of *valid* refresh token JTI values in memory.
#   On logout, the JTI is removed → that refresh token can no longer be used.
#   LIMITATION: this in-memory set is lost on server restart.
#   For production with multiple workers, swap this for a Redis set or a
#   dedicated `refresh_tokens` DB table. The interface (issue/check/revoke)
#   is the same — only the storage backend changes.
# ==========================================

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from jose import JWTError

from app.database import get_db
from app.models import User
from app.schemas import (
    SignupRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
    RefreshRequest,
    ChangePasswordRequest,
)
from app.auth.utils import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from app.auth.dependencies import get_current_user
from app.config import get_settings

# Pre-computed dummy hash used for constant-time password checks when a user
# is not found (prevents timing-based email enumeration).
# Generated once at module load — guaranteed to be a valid bcrypt hash.
_DUMMY_HASH: str = hash_password("timing-resistance-dummy-__never_matches__")

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# In-memory refresh token store
# Key:   jti (unique token ID string)
# Value: user_id (int)
# ---------------------------------------------------------------------------
# This is intentionally simple. To scale to multiple workers, replace with:
#   - Redis: SET jti user_id EX <7days_in_seconds>  / EXISTS jti / DEL jti
#   - DB table: INSERT / SELECT / DELETE on a refresh_tokens table
# ---------------------------------------------------------------------------

_valid_refresh_tokens: dict[str, int] = {}


# ---------------------------------------------------------------------------
# POST /auth/signup
# ---------------------------------------------------------------------------

@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account",
)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    """
    Creates a new user account.

    - Email must be unique (returns 409 if already taken).
    - Password is hashed with bcrypt before storage — never stored in plaintext.
    - Returns the created user (no tokens — user must login separately).
    """
    hashed = hash_password(req.password)
    user = User(email=req.email, hashed_password=hashed)
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        logger.warning("Signup attempt with duplicate email: %s", req.email)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    logger.info("New user registered: user_id=%s email=%s", user.id, user.email)
    return user


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive access + refresh tokens",
)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticates the user and returns JWT tokens.

    - Returns a short-lived access token (default: 15 min) and a long-lived
      refresh token (7 days).
    - The access token is used on every authenticated request.
    - The refresh token is used ONLY to obtain a new access token when the
      current one expires (via POST /auth/refresh).

    Security: Returns a generic "Invalid credentials" error for both
    "email not found" and "wrong password" to prevent email enumeration.
    """
    # Fetch user by email
    user = db.query(User).filter(User.email == req.email).first()

    # Constant-time check: always call verify_password even if user is None,
    # using the module-level _DUMMY_HASH, to prevent timing-based email enumeration.
    # It will always return False — that's intentional. The point is to spend the
    # same ~300 ms that a real hash check would take, preventing timing-based
    # email enumeration attacks.
    provided_hash = user.hashed_password if user else _DUMMY_HASH
    password_ok = verify_password(req.password, provided_hash)

    if not user or not password_ok:
        logger.warning("Failed login attempt for email: %s", req.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Issue tokens
    token_data = {"sub": str(user.id)}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Decode the refresh token just to extract its jti for storage
    refresh_payload = decode_refresh_token(refresh_token)
    jti = refresh_payload["jti"]
    _valid_refresh_tokens[jti] = user.id

    logger.info("User logged in: user_id=%s", user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------

@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange a refresh token for a new access token",
)
def refresh_token(req: RefreshRequest, db: Session = Depends(get_db)):
    """
    Issues a new access token (and rotates the refresh token) given a valid
    refresh token.

    Token rotation: the old refresh token is invalidated and a new one is
    issued. This limits the window for a stolen refresh token to be reused.
    """
    invalid_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_refresh_token(req.refresh_token)
    except JWTError:
        raise invalid_exc

    jti = payload.get("jti")
    user_id_str = payload.get("sub")

    # Validate against server-side store (prevents reuse after logout)
    if not jti or jti not in _valid_refresh_tokens:
        logger.warning("Refresh attempt with unknown or revoked jti: %s", jti)
        raise invalid_exc

    # Confirm user still exists
    try:
        user_id = int(user_id_str)
    except (TypeError, ValueError):
        raise invalid_exc

    user = db.get(User, user_id)
    if user is None:
        logger.warning("Refresh token references deleted user_id=%s", user_id)
        _valid_refresh_tokens.pop(jti, None)
        raise invalid_exc

    # Rotate: revoke old refresh token, issue new pair
    del _valid_refresh_tokens[jti]

    token_data = {"sub": str(user.id)}
    new_access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)

    new_payload = decode_refresh_token(new_refresh_token)
    new_jti = new_payload["jti"]
    _valid_refresh_tokens[new_jti] = user.id

    logger.info("Tokens rotated for user_id=%s", user.id)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------

@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout — invalidate the refresh token",
)
def logout(
    req: RefreshRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Invalidates the user's refresh token so it can no longer be used to
    obtain new access tokens.

    The user must still wait for their current access token to expire
    (up to 15 min). For immediate invalidation of access tokens, use
    a short expiry or a token blocklist (Redis).
    """
    try:
        payload = decode_refresh_token(req.refresh_token)
        jti = payload.get("jti")
        if jti and jti in _valid_refresh_tokens:
            del _valid_refresh_tokens[jti]
            logger.info("Refresh token revoked for user_id=%s (jti=%s)", current_user.id, jti)
        else:
            logger.info("Logout with already-revoked or unknown token for user_id=%s", current_user.id)
    except JWTError:
        # If the refresh token is already invalid, that's fine — logout succeeds.
        logger.info("Logout with invalid refresh token for user_id=%s — no-op.", current_user.id)

    # 204 No Content — no return value needed


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user info",
)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Returns the profile of the currently authenticated user.
    Useful for the frontend to verify the session is active and display user info.
    """
    return current_user


# ---------------------------------------------------------------------------
# POST /auth/change-password
# ---------------------------------------------------------------------------

@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change the authenticated user's password",
)
def change_password(
    req: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Verifies the user's current password then replaces it with the new one.
    Returns 400 if the current password is wrong.
    Returns 204 No Content on success.
    """
    if not verify_password(req.current_password, current_user.hashed_password):
        logger.warning("Change-password: wrong current password for user_id=%s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    current_user.hashed_password = hash_password(req.new_password)
    db.commit()
    logger.info("Password changed for user_id=%s", current_user.id)
    # 204 No Content — no return value needed

