# ==========================================
# tests/test_summary.py — GET /finance/summary Tests (Neon DB)
# ==========================================
# Tests against the real Neon PostgreSQL database, same conventions as
# test_finance.py: all test emails use @testdomain.dev, wiped by the
# autouse cleanup fixture in conftest.py after every test.
#
# /finance/summary computes current-calendar-month vs. previous-calendar-month
# revenue/expenses/net-profit/savings-rate, plus all-time total_entries and
# largest_expense (service.get_summary in app/finance/service.py). Because the
# bucketing is relative to "now", entries are seeded with dates computed from
# the real current date rather than hardcoded — mirroring exactly how
# get_summary() computes "today" (UTC) so tests stay correct regardless of
# when they're run.
# ==========================================

import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta

from app.database import SessionLocal
from app.models import User, FinanceEntry


# ---------------------------------------------------------------------------
# Date helpers — mirror service.get_summary()'s month bucketing exactly
# ---------------------------------------------------------------------------

def _today_utc():
    return datetime.now(timezone.utc).date()


def _current_month_date(day: int = 10) -> str:
    today = _today_utc()
    return today.replace(day=min(day, 28)).isoformat()


def _previous_month_date(day: int = 10) -> str:
    today = _today_utc()
    last_day_of_prev_month = today.replace(day=1) - timedelta(days=1)
    return last_day_of_prev_month.replace(day=min(day, 28)).isoformat()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def summary_user(client):
    """
    Creates one authenticated user for summary tests. Returns (user_id, tokens).
    Callers seed FinanceEntry rows directly via _seed() — bypassing the LLM
    entirely, same approach as test_finance.py::two_users_with_data.
    """
    client.post("/auth/signup", json={"email": "summary_alice@testdomain.dev", "password": "alice_pass_123"})
    login = client.post("/auth/login", json={"email": "summary_alice@testdomain.dev", "password": "alice_pass_123"})
    tokens = login.json()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "summary_alice@testdomain.dev").first()
        user_id = user.id
    finally:
        db.close()

    return user_id, tokens


def _seed(user_id, entries):
    """entries: list of (purchased, categorization, amount: Decimal, date_str, payment_type)."""
    db = SessionLocal()
    try:
        db.add_all([
            FinanceEntry(
                user_id=user_id, purchased=p, categorization=c,
                amount=a, date=d, payment_type=pt,
            )
            for (p, c, a, d, pt) in entries
        ])
        db.commit()
    finally:
        db.close()


# ===========================================================================
# Unauthenticated access
# ===========================================================================

class TestUnauthenticated:
    def test_summary_requires_auth(self, client):
        res = client.get("/finance/summary")
        assert res.status_code == 401


# ===========================================================================
# Empty state — freshly registered user, no transactions at all
# ===========================================================================

class TestEmptyState:
    def test_new_user_has_zeroed_summary(self, client):
        client.post("/auth/signup", json={"email": "summary_empty@testdomain.dev", "password": "pass12345"})
        tokens = client.post(
            "/auth/login", json={"email": "summary_empty@testdomain.dev", "password": "pass12345"}
        ).json()

        res = client.get("/finance/summary", headers={"Authorization": f"Bearer {tokens['access_token']}"})
        assert res.status_code == 200
        data = res.json()["data"]

        assert Decimal(str(data["revenue"]["value"])) == Decimal("0")
        assert Decimal(str(data["expenses"]["value"])) == Decimal("0")
        assert Decimal(str(data["net_profit"]["value"])) == Decimal("0")
        assert data["revenue"]["change_pct"] is None
        assert data["expenses"]["change_pct"] is None
        assert data["net_profit"]["change_pct"] is None
        assert data["savings_rate"]["value"] == 0
        assert data["savings_rate"]["change_pts"] is None
        assert data["total_entries"] == 0
        assert Decimal(str(data["largest_expense"])) == Decimal("0")


# ===========================================================================
# Month-over-month math
# ===========================================================================

class TestMonthOverMonthMath:
    def test_revenue_expenses_and_trend_computed_correctly(self, client, summary_user):
        """Verifies the actual KPI numbers and % trends, not just presence of fields."""
        user_id, tokens = summary_user
        cur, prev = _current_month_date(10), _previous_month_date(10)

        _seed(user_id, [
            ("Salary",    "Income",         Decimal("1000.00"), cur,  None),
            ("Groceries", "Food & Dining",  Decimal("-200.00"), cur,  "Card"),
            ("Salary",    "Income",         Decimal("800.00"),  prev, None),
            ("Groceries", "Food & Dining",  Decimal("-100.00"), prev, "Card"),
        ])

        res = client.get("/finance/summary", headers={"Authorization": f"Bearer {tokens['access_token']}"})
        assert res.status_code == 200
        data = res.json()["data"]

        # Current month: revenue 1000, expenses 200, net profit 800
        assert Decimal(str(data["revenue"]["value"]))    == Decimal("1000.00")
        assert Decimal(str(data["expenses"]["value"]))   == Decimal("200.00")
        assert Decimal(str(data["net_profit"]["value"])) == Decimal("800.00")

        # Trend vs. previous month (revenue 800, expenses 100, net 700):
        #   revenue: (1000-800)/800*100  = 25%
        #   expenses: (200-100)/100*100  = 100%
        #   net:     (800-700)/700*100   ≈ 14.29%
        assert data["revenue"]["change_pct"]    == pytest.approx(25.0,     abs=0.01)
        assert data["expenses"]["change_pct"]   == pytest.approx(100.0,    abs=0.01)
        assert data["net_profit"]["change_pct"] == pytest.approx(14.2857, abs=0.01)

        # Savings rate: current = 800/1000*100 = 80.0, previous = 700/800*100 = 87.5
        assert data["savings_rate"]["value"]      == pytest.approx(80.0, abs=0.1)
        assert data["savings_rate"]["change_pts"] == pytest.approx(-7.5, abs=0.1)

    def test_no_previous_month_data_yields_null_change_not_fake_percent(self, client, summary_user):
        """
        No prior-period baseline (e.g. a brand-new account) must report change
        as null, not a fabricated +100%/0% — this is what MetricsCards.jsx on
        the frontend uses to decide whether to render a trend badge at all.
        """
        user_id, tokens = summary_user
        cur = _current_month_date(5)

        _seed(user_id, [("Freelance", "Income", Decimal("500.00"), cur, None)])

        res = client.get("/finance/summary", headers={"Authorization": f"Bearer {tokens['access_token']}"})
        data = res.json()["data"]

        assert Decimal(str(data["revenue"]["value"])) == Decimal("500.00")
        assert data["revenue"]["change_pct"]      is None
        assert data["expenses"]["change_pct"]     is None
        assert data["net_profit"]["change_pct"]   is None
        assert data["savings_rate"]["change_pts"] is None
        assert data["savings_rate"]["value"] == pytest.approx(100.0, abs=0.1)

    def test_entries_outside_current_and_previous_month_excluded_from_trend(self, client, summary_user):
        """
        An old entry (e.g. from years ago) must not pollute the current/previous
        month comparison, but must still count toward the all-time total_entries
        and largest_expense figures.
        """
        user_id, tokens = summary_user
        cur = _current_month_date(5)

        _seed(user_id, [
            ("Old rent", "Housing",        Decimal("-5000.00"), "2020-01-01", "Bank Transfer"),
            ("Coffee",   "Food & Dining",  Decimal("-3.00"),    cur,          "Card"),
        ])

        res = client.get("/finance/summary", headers={"Authorization": f"Bearer {tokens['access_token']}"})
        data = res.json()["data"]

        # The 2020 entry must not appear in current-month expenses
        assert Decimal(str(data["expenses"]["value"])) == Decimal("3.00")
        # ...but is still reflected in all-time aggregates
        assert data["total_entries"] == 2
        assert Decimal(str(data["largest_expense"])) == Decimal("5000.00")


# ===========================================================================
# User isolation
# ===========================================================================

class TestUserIsolation:
    def test_summary_does_not_leak_across_users(self, client):
        cur = _current_month_date(12)

        client.post("/auth/signup", json={"email": "summary_a@testdomain.dev", "password": "pass12345"})
        tok_a = client.post("/auth/login", json={"email": "summary_a@testdomain.dev", "password": "pass12345"}).json()
        client.post("/auth/signup", json={"email": "summary_b@testdomain.dev", "password": "pass12345"})
        tok_b = client.post("/auth/login", json={"email": "summary_b@testdomain.dev", "password": "pass12345"}).json()

        db = SessionLocal()
        try:
            user_a = db.query(User).filter(User.email == "summary_a@testdomain.dev").first()
            user_b = db.query(User).filter(User.email == "summary_b@testdomain.dev").first()
            db.add_all([
                FinanceEntry(user_id=user_a.id, purchased="A Income", categorization="Income",
                             amount=Decimal("1000.00"), date=cur, payment_type=None),
                FinanceEntry(user_id=user_b.id, purchased="B Income", categorization="Income",
                             amount=Decimal("50.00"), date=cur, payment_type=None),
            ])
            db.commit()
        finally:
            db.close()

        res_a = client.get("/finance/summary", headers={"Authorization": f"Bearer {tok_a['access_token']}"})
        res_b = client.get("/finance/summary", headers={"Authorization": f"Bearer {tok_b['access_token']}"})

        assert Decimal(str(res_a.json()["data"]["revenue"]["value"])) == Decimal("1000.00")
        assert Decimal(str(res_b.json()["data"]["revenue"]["value"])) == Decimal("50.00")


# ===========================================================================
# Totals are all-time, not capped like /finance/recent (limit=5)
# ===========================================================================

class TestTotalsAreAllTimeNotCapped:
    def test_total_entries_and_largest_expense_beyond_recent_limit(self, client, summary_user):
        """
        /finance/recent caps at 5 rows server-side — summary must NOT inherit
        that limit (this is the exact bug the dashboard's Quick Stats card had
        before it was switched to read from /finance/summary).
        """
        user_id, tokens = summary_user
        cur = _current_month_date(1)
        entries = [
            (f"Item {i}", "Other", Decimal(f"-{i + 1}.00"), cur, None)
            for i in range(8)
        ]
        _seed(user_id, entries)

        res = client.get("/finance/summary", headers={"Authorization": f"Bearer {tokens['access_token']}"})
        data = res.json()["data"]

        assert data["total_entries"] == 8
        assert Decimal(str(data["largest_expense"])) == Decimal("8.00")
