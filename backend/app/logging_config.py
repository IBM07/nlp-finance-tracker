# ==========================================
# logging_config.py — Centralised Logging Setup
# ==========================================
# Call setup_logging() once at app startup (in main.py).
# All other modules just do: logger = logging.getLogger(__name__)
# ==========================================

import logging
import sys
from pathlib import Path


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure root logger with:
      - StreamHandler (stdout) for Render / container environments
      - FileHandler  (backend.log) for local dev inspection

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

    # --- file handler (local dev) ---
    log_file = Path("backend.log")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    # --- Root logger ---
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()          # avoid duplicate handlers on reload
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)

    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
