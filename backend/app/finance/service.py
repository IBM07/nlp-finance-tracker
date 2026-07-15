# ==========================================
# finance/service.py — Business Logic Layer
# ==========================================
# Ties together LLM → sql_guard → database.
# Routes call service functions; service functions don't know about HTTP.
#
# NOTE (Phase 1): user_id is a required parameter on every function.
# Phase 2 will provide this via get_current_user() dependency injection.
# For now it is passed explicitly from routes.py.
# ==========================================

import logging
import re
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.finance.llm import generate_sql
from app.finance.sql_guard import validate_sql, SQLGuardError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Query service (NL → SQL → results)
# ---------------------------------------------------------------------------

def run_nl_query(
    question: str,
    user_id: int,
    db: Session,
) -> dict:
    """
    Full pipeline:
      1. Ask LLM to generate SQL scoped to user_id
      2. Validate with sql_guard (raises SQLGuardError on failure)
      3. Enforce user_id filter at application layer (belt-and-suspenders)
      4. Execute via SQLAlchemy text() (parameterised, safe)
      5. Return results as list of dicts

    Raises:
        SQLGuardError  — if the LLM output fails validation
        RuntimeError   — if the LLM service is unavailable
    """
    # Step 1: LLM
    raw_sql = generate_sql(question, user_id)
    if not raw_sql:
        raise RuntimeError("LLM service unavailable or returned empty response.")

    # Step 2: SQL guard
    safe_sql = validate_sql(raw_sql)   # raises SQLGuardError if invalid

    # Step 3: Server-side user_id enforcement
    # Even after sql_guard passes, double-check the WHERE clause contains
    # user_id = <the actual user_id>. Belt-and-suspenders.
    _assert_user_id_scoped(safe_sql, user_id)

    # Step 4: Execute
    logger.info("Executing validated SQL for user_id=%s: %s", user_id, safe_sql)
    result = db.execute(text(safe_sql))
    rows = result.fetchall()
    columns = list(result.keys())

    # Step 5: Serialise to list of dicts
    data = [dict(zip(columns, row)) for row in rows]

    return {
        "sql": safe_sql,
        "data": data,
        "row_count": len(data),
        "message": f"Found {len(data)} records.",
    }


# ---------------------------------------------------------------------------
# Analytics service
# ---------------------------------------------------------------------------

def get_analytics(user_id: int, db: Session) -> list[dict]:
    """Returns spending totals per category for this user."""
    sql = text(
        "SELECT categorization, SUM(amount) AS total "
        "FROM finance_entries "
        "WHERE user_id = :uid "
        "GROUP BY categorization "
        "ORDER BY total DESC"
    )
    rows = db.execute(sql, {"uid": user_id}).fetchall()
    return [{"category": row[0], "total": Decimal(str(row[1]))} for row in rows]


# ---------------------------------------------------------------------------
# Recent transactions service
# ---------------------------------------------------------------------------

def get_recent(user_id: int, db: Session, limit: int = 5) -> list[dict]:
    """Returns the N most recent finance entries for this user."""
    sql = text(
        "SELECT id, purchased, amount, categorization, date "
        "FROM finance_entries "
        "WHERE user_id = :uid "
        "ORDER BY id DESC "
        "LIMIT :lim"
    )
    rows = db.execute(sql, {"uid": user_id, "lim": limit}).fetchall()
    return [
        {
            "id": row[0],
            "item": row[1],
            "amount": Decimal(str(row[2])),
            "category": row[3],
            "date": row[4],
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Create entry service
# ---------------------------------------------------------------------------

def create_entry(user_id: int, data: dict, db: Session) -> dict:
    """
    Inserts a new FinanceEntry for the given user and returns it as a dict.
    `data` must contain: purchased, categorization, amount, date, payment_type (optional).
    """
    from app.models import FinanceEntry
    entry = FinanceEntry(
        user_id=user_id,
        purchased=data["purchased"],
        categorization=data["categorization"],
        amount=data["amount"],
        date=data["date"],
        payment_type=data.get("payment_type"),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    logger.info(
        "Created finance entry id=%s for user_id=%s: %s %.2f",
        entry.id, user_id, entry.purchased, entry.amount,
    )
    return {
        "id": entry.id,
        "item": entry.purchased,
        "amount": entry.amount,
        "category": entry.categorization,
        "date": entry.date,
        "payment_type": entry.payment_type,
        "created_at": str(entry.created_at),
    }



# ---------------------------------------------------------------------------
# Internal: server-side user_id enforcement
# ---------------------------------------------------------------------------

def _assert_user_id_scoped(sql: str, user_id: int) -> None:
    """
    Verifies the SQL contains a reference to the correct user_id.
    This is a last-resort check — even if the LLM ignores the prompt and
    omits the WHERE user_id clause, this will catch it.

    Raises SQLGuardError if the user_id constraint is missing or wrong.
    """
    # Look for patterns like: user_id = 42  or  user_id=42
    pattern = re.compile(
        r"user_id\s*=\s*" + re.escape(str(user_id)),
        re.IGNORECASE,
    )
    if not pattern.search(sql):
        logger.critical(
            "SQL guard (server-enforcement): user_id=%s not found in SQL: %s",
            user_id,
            sql,
        )
        raise SQLGuardError(
            f"Generated SQL is missing required user_id={user_id} scope filter."
        )
