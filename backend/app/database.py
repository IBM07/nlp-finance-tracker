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
