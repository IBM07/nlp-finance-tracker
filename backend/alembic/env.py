# ==========================================
# alembic/env.py — Migration Environment
# ==========================================
# Wired to:
#   - Read DATABASE_URL from .env (via app.config)
#   - Import app.models so autogenerate detects all table changes
# ==========================================

import sys
import os
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# ---------------------------------------------------------------------------
# Make "backend/" importable so "from app.xxx import yyy" works
# when Alembic is run from the backend/ directory.
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent          # alembic/
BACKEND_DIR = HERE.parent                        # backend/
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# ---------------------------------------------------------------------------
# Load app config & models
# ---------------------------------------------------------------------------
from app.config import get_settings             # noqa: E402
from app.database import Base                   # noqa: E402
from app import models                          # noqa: E402, F401  — registers all tables

settings = get_settings()

# ---------------------------------------------------------------------------
# Alembic Config object
# ---------------------------------------------------------------------------
config = context.config

# Override the sqlalchemy.url from alembic.ini with the one from .env
config.set_main_option("sqlalchemy.url", settings.database_url)

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata — gives autogenerate the full schema picture
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """
    Offline mode: emit SQL to stdout without a live DB connection.
    Useful for reviewing what changes will be applied.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,      # detect column type changes
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Online mode: connect to the DB and run migrations directly.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
