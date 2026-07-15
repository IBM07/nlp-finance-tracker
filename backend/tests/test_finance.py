# ==========================================
# tests/test_finance.py — Finance Endpoint Tests (Neon DB)
# ==========================================
# Tests against the real Neon PostgreSQL database.
# All test emails use @testdomain.dev — wiped by the autouse
# cleanup fixture in conftest.py after every test.
#
# Critical security test: a user MUST NOT be able to see another user's data.
# This validates user_id scoping at every layer: auth dependency → service → SQL.
#
# Also tests:
#   - Unauthenticated access is rejected (all finance routes require auth)
#   - /finance/analytics and /finance/recent return only the caller's data
#
# NOTE: /finance/query (LLM path) is NOT tested here — it requires a live
# Groq API call. Test that separately or mock the LLM in CI.
# ==========================================

import pytest
from decimal import Decimal
from sqlalchemy import text

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import User, FinanceEntry
from app.auth.utils import hash_password


# ---------------------------------------------------------------------------
# Fixture: two users with seeded finance data
# ---------------------------------------------------------------------------

@pytest.fixture
def two_users_with_data(client):
    """
    Creates two separate users via the API, seeds finance entries directly
    into Neon, and returns their tokens.

    Returns (tokens_user1, tokens_user2).
    Cleanup is handled by the autouse fixture in conftest.py.
    """
    # Signup + login — User 1 (Alice)
    client.post("/auth/signup", json={"email": "alice@testdomain.dev", "password": "alice_pass_123"})
    login1  = client.post("/auth/login",  json={"email": "alice@testdomain.dev", "password": "alice_pass_123"})
    tokens1 = login1.json()

    # Signup + login — User 2 (Bob)
    client.post("/auth/signup", json={"email": "bob@testdomain.dev", "password": "bob_pass_456"})
    login2  = client.post("/auth/login",  json={"email": "bob@testdomain.dev", "password": "bob_pass_456"})
    tokens2 = login2.json()

    # Seed finance entries directly so we don't need a working LLM
    db = SessionLocal()
    try:
        user1 = db.query(User).filter(User.email == "alice@testdomain.dev").first()
        user2 = db.query(User).filter(User.email == "bob@testdomain.dev").first()

        db.add_all([
            FinanceEntry(user_id=user1.id, purchased="Coffee",  categorization="Food",
                         amount=Decimal("4.50"),    date="2025-01-01", payment_type="Card"),
            FinanceEntry(user_id=user1.id, purchased="Rent",    categorization="Utilities",
                         amount=Decimal("1200.00"), date="2025-01-01", payment_type="Bank Transfer"),
            FinanceEntry(user_id=user2.id, purchased="Gym",     categorization="Healthcare",
                         amount=Decimal("60.00"),   date="2025-01-01", payment_type="Card"),
            FinanceEntry(user_id=user2.id, purchased="Netflix", categorization="Entertainment",
                         amount=Decimal("15.99"),   date="2025-01-01", payment_type="Card"),
        ])
        db.commit()
    finally:
        db.close()

    return tokens1, tokens2


# ===========================================================================
# Unauthenticated access
# ===========================================================================

class TestUnauthenticated:
    def test_analytics_requires_auth(self, client):
        res = client.get("/finance/analytics")
        assert res.status_code == 401

    def test_recent_requires_auth(self, client):
        res = client.get("/finance/recent")
        assert res.status_code == 401

    def test_query_requires_auth(self, client):
        res = client.post("/finance/query", json={"question": "show all expenses"})
        assert res.status_code == 401


# ===========================================================================
# User isolation (most critical tests)
# ===========================================================================

class TestUserIsolation:
    def test_analytics_returns_only_own_data(self, client, two_users_with_data):
        """Alice's analytics must contain only Alice's categories."""
        tokens1, tokens2 = two_users_with_data

        res1 = client.get("/finance/analytics", headers={"Authorization": f"Bearer {tokens1['access_token']}"})
        res2 = client.get("/finance/analytics", headers={"Authorization": f"Bearer {tokens2['access_token']}"})

        assert res1.status_code == 200
        assert res2.status_code == 200

        cats1 = {item["category"] for item in res1.json()["data"]}
        cats2 = {item["category"] for item in res2.json()["data"]}

        # Alice has Food and Utilities — must NOT see Bob's data
        assert "Food"          in cats1
        assert "Utilities"     in cats1
        assert "Healthcare"    not in cats1
        assert "Entertainment" not in cats1

        # Bob has Healthcare and Entertainment — must NOT see Alice's data
        assert "Healthcare"    in cats2
        assert "Entertainment" in cats2
        assert "Food"          not in cats2
        assert "Utilities"     not in cats2

    def test_recent_returns_only_own_transactions(self, client, two_users_with_data):
        """Alice's recent transactions must only show Alice's entries."""
        tokens1, tokens2 = two_users_with_data

        res1 = client.get("/finance/recent", headers={"Authorization": f"Bearer {tokens1['access_token']}"})
        res2 = client.get("/finance/recent", headers={"Authorization": f"Bearer {tokens2['access_token']}"})

        assert res1.status_code == 200
        assert res2.status_code == 200

        items1 = {row["item"] for row in res1.json()["data"]}
        items2 = {row["item"] for row in res2.json()["data"]}

        # Alice sees Coffee and Rent — not Gym or Netflix
        assert "Coffee"  in items1
        assert "Rent"    in items1
        assert "Gym"     not in items1
        assert "Netflix" not in items1

        # Bob sees Gym and Netflix — not Coffee or Rent
        assert "Gym"     in items2
        assert "Netflix" in items2
        assert "Coffee"  not in items2
        assert "Rent"    not in items2

    def test_analytics_amounts_are_correct_per_user(self, client, two_users_with_data):
        """Totals must match only that user's data — not the combined total."""
        tokens1, _ = two_users_with_data

        res = client.get("/finance/analytics", headers={"Authorization": f"Bearer {tokens1['access_token']}"})
        assert res.status_code == 200

        data = {item["category"]: float(item["total"]) for item in res.json()["data"]}

        # Alice: Food = 4.50, Utilities = 1200.00
        assert pytest.approx(data.get("Food"),      0.01) == 4.50
        assert pytest.approx(data.get("Utilities"), 0.01) == 1200.00
        # Bob's categories must NOT appear at all
        assert "Healthcare"    not in data
        assert "Entertainment" not in data


# ===========================================================================
# Own data visibility
# ===========================================================================

class TestOwnDataVisible:
    def test_user_can_see_own_recent(self, client, two_users_with_data):
        tokens1, _ = two_users_with_data
        res = client.get("/finance/recent", headers={"Authorization": f"Bearer {tokens1['access_token']}"})
        assert res.status_code == 200
        assert len(res.json()["data"]) == 2   # Alice has exactly 2 entries

    def test_user_sees_no_data_if_empty(self, client):
        """A freshly registered user must see empty results — no cross-user data leak."""
        client.post("/auth/signup", json={"email": "newuser@testdomain.dev", "password": "newpassword99"})
        tokens = client.post("/auth/login", json={"email": "newuser@testdomain.dev", "password": "newpassword99"}).json()

        res_analytics = client.get("/finance/analytics", headers={"Authorization": f"Bearer {tokens['access_token']}"})
        res_recent    = client.get("/finance/recent",    headers={"Authorization": f"Bearer {tokens['access_token']}"})

        assert res_analytics.status_code == 200
        assert res_analytics.json()["data"] == []

        assert res_recent.status_code == 200
        assert res_recent.json()["data"] == []
