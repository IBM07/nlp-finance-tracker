# ==========================================
# database.py — SQLAlchemy Database Layer (Neon PostgreSQL)
# ==========================================
# Provides:
#   - engine:       SQLAlchemy Engine (Neon Postgres via DATABASE_URL)
#   - SessionLocal: Session factory used to create per-request DB sessions
#   - Base:         Declarative base — all models inherit from this
#   - get_db():     FastAPI dependency that yields a session and guarantees cleanup
#
# DATABASE_URL is read from the DATABASE_URL env var (set in .env).
# NullPool is used because Neon is serverless — it closes connections after
# every transaction, so pooling would cause "connection already closed" errors.
# ==========================================

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import get_settings


settings = get_settings()

# ---------------------------------------------------------------------------
# Engine — Neon PostgreSQL only
# ---------------------------------------------------------------------------

engine = create_engine(
    settings.database_url,
    poolclass=NullPool,   # Required for Neon serverless — avoids stale connections
)

# ---------------------------------------------------------------------------
# Session Factory
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    # expire_on_commit=False: by default SQLAlchemy expires every attribute on
    # commit, so the next attribute access (e.g. entry.id in a route handler)
    # transparently issues a fresh SELECT. Under NullPool, commit() has already
    # closed the connection, so that "transparent" reload opens a brand-new one
    # against Neon — an operation that intermittently fails against a
    # serverless/cold-start endpoint, turning a successful write into a 500.
    # Postgres already returns generated values (PK, server_default columns)
    # via RETURNING during flush, before commit — so attributes are correct
    # without a post-commit reload; this setting just stops SQLAlchemy from
    # discarding and re-fetching them.
    expire_on_commit=False,
    bind=engine,
)

# ---------------------------------------------------------------------------
# Declarative Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """All SQLAlchemy models inherit from this."""
    pass


# ---------------------------------------------------------------------------
# FastAPI Dependency
# ---------------------------------------------------------------------------

def get_db():
    """
    Yields a SQLAlchemy session for the duration of a single HTTP request.
    The finally block guarantees the session is closed even if the handler
    raises an exception — prevents connection leaks.

    Usage in a route:
        from app.database import get_db
        from sqlalchemy.orm import Session
        from fastapi import Depends

        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
