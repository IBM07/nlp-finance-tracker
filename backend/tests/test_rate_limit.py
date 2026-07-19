# ==========================================
# tests/test_rate_limit.py — Rate Limiting (Phase D, item 1)
# ==========================================
# Verifies the 10/minute cap on POST /finance/chat (Section 6.4 of the
# feature plan). classify_and_extract is mocked so this exercises only the
# slowapi rate-limit middleware, never a live Groq call.
#
# The shared `limiter` (app/middleware/rate_limit.py) keys on remote address,
# and TestClient requests all appear to come from the same address, so every
# test here resets the limiter's in-memory storage first — otherwise hits
# from other tests hitting /finance/chat in the same process/minute would
# leak in and make these tests order-dependent.
# ==========================================

from decimal import Decimal
from unittest.mock import patch

import pytest

from app.database import SessionLocal
from app.middleware.rate_limit import limiter
from app.models import User
from app.schemas import IntentAdd


@pytest.fixture(autouse=True)
def reset_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def alice(client):
    client.post("/auth/signup", json={"email": "ratelimit_alice@testdomain.dev", "password": "alice_pass_123"})
    login = client.post("/auth/login", json={"email": "ratelimit_alice@testdomain.dev", "password": "alice_pass_123"})
    tokens = login.json()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "ratelimit_alice@testdomain.dev").first()
        return user.id, tokens
    finally:
        db.close()


class TestChatRateLimit:
    def test_11th_request_within_a_minute_is_rejected(self, client, alice):
        """
        Section 6.4: "Rate limit on /finance/chat: 10 requests/minute". The
        11th request inside the same window must be rejected with 429 —
        anything else means the LLM (the most expensive call in the app)
        has no cap and is exposed to unbounded cost / abuse.
        """
        _, tokens = alice
        intent_data = IntentAdd(
            purchased="Coffee", categorization="Food & Dining",
            amount=Decimal("5"), type="expense", date="today", payment_type=None,
        )
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        with patch("app.finance.routes.classify_and_extract", return_value=intent_data):
            statuses = [
                client.post("/finance/chat", json={"message": "Add 5 coffee"}, headers=headers).status_code
                for _ in range(11)
            ]

        assert statuses[:10] == [200] * 10
        assert statuses[10] == 429

    def test_limit_is_per_route_not_global(self, client, alice):
        """
        Exhausting /finance/chat's 10/minute budget must not throttle other
        finance routes (e.g. /finance/recent, which is capped at 60/minute) —
        each route's @limiter.limit() decorator is independent.
        """
        _, tokens = alice
        intent_data = IntentAdd(
            purchased="Coffee", categorization="Food & Dining",
            amount=Decimal("5"), type="expense", date="today", payment_type=None,
        )
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        with patch("app.finance.routes.classify_and_extract", return_value=intent_data):
            for _ in range(10):
                client.post("/finance/chat", json={"message": "Add 5 coffee"}, headers=headers)

        res = client.get("/finance/recent", headers=headers)
        assert res.status_code == 200
