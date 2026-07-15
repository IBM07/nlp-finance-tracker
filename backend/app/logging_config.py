# ==========================================
# logging_config.py — Centralised Logging Setup
# ==========================================
# Call setup_logging() once at app startup (in main.py).
# All other modules just do: logger = logging.getLogger(__name__)
# ==========================================

import logging
import os
import sys
from pathlib import Path


def _is_production() -> bool:
    """
    Returns True when the app is running in a production / cloud environment.

    Detection logic (any one is enough):
      1. ENVIRONMENT env var is explicitly set to "production"
      2. DATABASE_URL starts with "postgresql" (i.e., Neon / Render Postgres)

    In production we skip the file handler because:
      - The filesystem is ephemeral (logs would be lost on restart anyway)
      - Render captures stdout and shows it in its log dashboard
      - Writing files in a read-only or ephemeral container can cause errors
    """
    env_flag = os.getenv("ENVIRONMENT", "").lower() == "production"
    db_url   = os.getenv("DATABASE_URL", "")
    pg_flag  = db_url.startswith("postgresql")
    return env_flag or pg_flag


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure root logger with:
      - StreamHandler (stdout) — always active; required for Render / containers
      - FileHandler  (backend.log) — LOCAL DEV ONLY; skipped in production

    Both handlers share the same formatter.
    Call this once from main.py before the app is created.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- stdout handler (always on) ---
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)

    # --- Root logger ---
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()          # avoid duplicate handlers on reload
    root_logger.addHandler(stream_handler)

    # --- file handler (LOCAL DEV ONLY — skipped in production) ---
    if not _is_production():
        log_file = Path("backend.log")
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
