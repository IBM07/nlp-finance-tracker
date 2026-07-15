# ==========================================
# tests/conftest.py — Shared Pytest Configuration
# ==========================================
# Strategy: test against the real Neon database.
#
# Why no SQLite / in-memory override?
#   - The application is Neon-only. SQLite has different SQL dialects,
#     different FK behaviour, and doesn't support Postgres-specific types.
#   - Testing on the real DB guarantees the behaviour you ship is what
#     you tested. SQLite mocks can hide real bugs.
#
# Isolation strategy (no SQLite transactions trick):
#   - Every test user is created with a unique email suffix so tests don't
#     collide with each other or with real data.
#   - After every test function the `cleanup_test_users` autouse fixture
#     deletes all rows in `finance_entries` and `users` where the email
#     contains the marker domain "@testdomain.dev".
#   - This keeps the Neon DB clean without needing a separate test DB.
# ==========================================

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.database import SessionLocal


# ---------------------------------------------------------------------------
# App client — shared across all tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def client():
    """FastAPI test client that hits the real Neon database via the live app."""
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Cleanup — runs after every single test function
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def cleanup_test_users():
    """
    Deletes all test data after each test.

    All tests MUST use emails ending in '@testdomain.dev'.
    This marker makes cleanup safe — it never touches real user data.
    """
    yield   # test runs here

    db = SessionLocal()
    try:
        # Delete finance entries first (FK constraint: entries reference users)
        db.execute(
            text("DELETE FROM finance_entries WHERE user_id IN "
                 "(SELECT id FROM users WHERE email LIKE '%@testdomain.dev')")
        )
        db.execute(
            text("DELETE FROM users WHERE email LIKE '%@testdomain.dev'")
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
