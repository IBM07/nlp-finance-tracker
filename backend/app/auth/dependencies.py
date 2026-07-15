# ==========================================
# auth/dependencies.py — FastAPI Auth Dependency
# ==========================================
# Provides get_current_user() — the single dependency that protects every
# authenticated route.
#
# Usage in any protected route:
#   from app.auth.dependencies import get_current_user
#   from app.models import User
#
#   @router.get("/me")
#   def me(current_user: User = Depends(get_current_user)):
#       return current_user
#
# Design:
#   - Reads the Bearer token from the Authorization header (OAuth2PasswordBearer).
#   - Decodes it with decode_access_token() — raises 401 on any JWT error.
#   - Fetches the User row from the DB to confirm the account still exists.
#   - Returns the ORM User object so callers can read user.id, user.email, etc.
# ==========================================

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.auth.utils import decode_access_token

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OAuth2 scheme — tells FastAPI/Swagger that routes using this dependency
# require a Bearer token in the Authorization header.
# tokenUrl points at our login endpoint so Swagger UI can test auth directly.
# ---------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ---------------------------------------------------------------------------
# Credentials exception — reused in both get_current_user variants
# ---------------------------------------------------------------------------

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials.",
    headers={"WWW-Authenticate": "Bearer"},
)


# ---------------------------------------------------------------------------
# Core dependency
# ---------------------------------------------------------------------------

def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency: extracts the current authenticated user from JWT.

    Flow:
        1. FastAPI extracts the Bearer token from the Authorization header.
        2. We decode it and validate the type claim ("access").
        3. We extract the "sub" claim (user_id as string).
        4. We fetch the User from the database.
        5. We return the User ORM object.

    Raises:
        401 Unauthorized — on any JWT error or if the user no longer exists.
    """
    try:
        payload = decode_access_token(token)
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            logger.warning("JWT missing 'sub' claim.")
            raise _CREDENTIALS_EXCEPTION
    except JWTError as e:
        logger.warning("JWT decode failed: %s", e)
        raise _CREDENTIALS_EXCEPTION

    # Validate user_id is a valid integer (guards against malformed tokens)
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        logger.warning("JWT 'sub' claim is not a valid integer: %r", user_id_str)
        raise _CREDENTIALS_EXCEPTION

    # Fetch user from DB — confirms account still exists (wasn't deleted)
    user = db.get(User, user_id)
    if user is None:
        logger.warning("JWT references non-existent user_id=%s", user_id)
        raise _CREDENTIALS_EXCEPTION

    logger.debug("Authenticated user_id=%s via JWT.", user_id)
    return user
