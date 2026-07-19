# ==========================================
# main.py — FastAPI Application Entrypoint
# ==========================================
# Responsibilities:
#   - Configure logging (once, at startup)
#   - Create the FastAPI app instance
#   - Register middleware (CORS, rate limiting)
#   - Mount all routers
#   - Startup hook: create DB tables if they don't exist
#
# Run locally:
#   uvicorn app.main:app --reload
# ==========================================

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.logging_config import setup_logging
from app.config import get_settings
from app.database import engine, Base
from app.middleware.rate_limit import limiter

# Import all models so SQLAlchemy knows about them before create_all()
from app import models  # noqa: F401

# Import routers
from app.finance.routes import router as finance_router
from app.auth.routes import router as auth_router

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Finance Tracker API",
    version="1.0.0",
    description="Natural-language personal finance tracker with multi-user support.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- Rate Limiter ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- CORS ---
# DEPLOY NOTE (Phase 4): Set ALLOWED_ORIGINS in .env to your Cloudflare Pages URL
# before going live. Example: ALLOWED_ORIGINS=https://yourapp.pages.dev
# Never leave "*" in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# --- Routers ---
app.include_router(finance_router)
app.include_router(auth_router)

# ---------------------------------------------------------------------------
# Startup event
# ---------------------------------------------------------------------------

@app.on_event("startup")
def on_startup():
    """
    Creates all tables defined by SQLAlchemy models if they don't exist.
    Safe to run every time — uses CREATE TABLE IF NOT EXISTS semantics.

    For production migrations use Alembic instead of this.
    This is kept for fast local dev iteration.
    """
    logger.info("Running startup: ensuring database tables exist...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ready.")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/", tags=["health"])
def health_check():
    return {
        "status": "ok",
        "service": "AI Finance Tracker API",
        "version": "1.0.0",
        "database": settings.database_url.split("@")[-1] if "@" in settings.database_url else "sqlite (local)",
    }
