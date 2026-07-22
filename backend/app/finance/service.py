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
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.finance.llm import generate_sql
from app.finance.sql_guard import validate_sql, SQLGuardError
from app.schemas import EDITABLE_FIELDS

logger = logging.getLogger(__name__)


class EntryNotFoundError(Exception):
    """Raised when a target FinanceEntry cannot be resolved for this user."""
    pass


_CENTS = Decimal("0.01")


def _to_money(value) -> Decimal:
    """
    Quantizes to 2 decimal places, matching the `amount` column's
    Numeric(10, 2) scale. Without this, a Decimal built from a bare int/float
    (e.g. Decimal(str(600)) == Decimal("600")) keeps its original precision
    in memory — Postgres would normalize it to "600.00" on write, but nothing
    reloads the row after commit (see database.py's expire_on_commit=False),
    so callers that read the in-memory value straight back (audit log
    snapshots, API responses) would otherwise see the unnormalized form.
    """
    return Decimal(str(value)).quantize(_CENTS)


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
# Summary service (KPI cards — current vs. previous month, all-time stats)
# ---------------------------------------------------------------------------

def _pct_change(current: Decimal, previous: Decimal) -> Optional[float]:
    """
    Relative percent change from `previous` to `current`.
    Returns None when there is no prior-period baseline to compare against
    (rather than fabricating a misleading +/-100%).
    """
    if previous == 0:
        return None
    return float((current - previous) / abs(previous) * 100)


def get_summary(user_id: int, db: Session) -> dict:
    """
    KPI figures for the dashboard metric cards: current-calendar-month
    revenue/expenses/net-profit/savings-rate, each compared against the
    previous calendar month, plus all-time entry count and largest expense.

    Computed in Python (not SQL aggregates) because per-user entry volumes
    are small and this keeps the month-bucketing logic readable/testable.
    """
    rows = db.execute(
        text("SELECT date, amount FROM finance_entries WHERE user_id = :uid"),
        {"uid": user_id},
    ).fetchall()

    today = datetime.now(timezone.utc).date()
    current_month = today.strftime("%Y-%m")
    previous_month = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    revenue_cur = expenses_cur = Decimal("0")
    revenue_prev = expenses_prev = Decimal("0")
    total_entries = 0
    largest_expense = Decimal("0")

    for date_str, raw_amount in rows:
        amount = Decimal(str(raw_amount))
        total_entries += 1
        if amount < 0 and -amount > largest_expense:
            largest_expense = -amount

        month = (date_str or "")[:7]
        if month == current_month:
            if amount > 0:
                revenue_cur += amount
            else:
                expenses_cur += -amount
        elif month == previous_month:
            if amount > 0:
                revenue_prev += amount
            else:
                expenses_prev += -amount

    net_cur = revenue_cur - expenses_cur
    net_prev = revenue_prev - expenses_prev
    savings_cur = float(net_cur / revenue_cur * 100) if revenue_cur > 0 else 0.0
    savings_prev = float(net_prev / revenue_prev * 100) if revenue_prev > 0 else 0.0
    savings_change = (savings_cur - savings_prev) if (revenue_cur > 0 and revenue_prev > 0) else None

    return {
        "revenue": {"value": revenue_cur, "change_pct": _pct_change(revenue_cur, revenue_prev)},
        "expenses": {"value": expenses_cur, "change_pct": _pct_change(expenses_cur, expenses_prev)},
        "net_profit": {"value": net_cur, "change_pct": _pct_change(net_cur, net_prev)},
        "savings_rate": {"value": round(savings_cur, 1), "change_pts": savings_change},
        "total_entries": total_entries,
        "largest_expense": largest_expense,
    }


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
# Paginated / filterable transactions list (Transactions page)
# ---------------------------------------------------------------------------

def list_entries(
    user_id: int,
    db: Session,
    limit: int = 20,
    offset: int = 0,
    category: Optional[str] = None,
    search: Optional[str] = None,
) -> dict:
    """
    Returns a paginated, optionally filtered slice of this user's finance
    entries, newest first, plus the total row count matching the filter
    (for the caller to compute page count). Reuses the composite
    (user_id, date) index that already backs get_recent()/get_summary().
    """
    where = ["user_id = :uid"]
    params: dict = {"uid": user_id}
    if category:
        where.append("categorization = :cat")
        params["cat"] = category
    if search:
        where.append("purchased ILIKE :search")
        params["search"] = f"%{search}%"
    where_sql = " AND ".join(where)

    total = db.execute(
        text(f"SELECT COUNT(*) FROM finance_entries WHERE {where_sql}"), params
    ).scalar()

    rows = db.execute(
        text(
            f"SELECT id, purchased, amount, categorization, date, payment_type "
            f"FROM finance_entries WHERE {where_sql} "
            f"ORDER BY date DESC, id DESC LIMIT :lim OFFSET :off"
        ),
        {**params, "lim": limit, "off": offset},
    ).fetchall()

    data = [
        {
            "id": row[0],
            "item": row[1],
            "amount": Decimal(str(row[2])),
            "category": row[3],
            "date": row[4],
            "payment_type": row[5],
        }
        for row in rows
    ]
    return {"data": data, "total": total, "limit": limit, "offset": offset}


# ---------------------------------------------------------------------------
# Monthly revenue/expense trend (Analytics page)
# ---------------------------------------------------------------------------

def get_monthly_trend(user_id: int, db: Session, months: int = 6) -> list[dict]:
    """
    Returns revenue/expense totals bucketed by calendar month for each of the
    last `months` months (oldest first), including months with no activity
    so the Analytics chart has a continuous x-axis.
    """
    rows = db.execute(
        text("SELECT date, amount FROM finance_entries WHERE user_id = :uid"),
        {"uid": user_id},
    ).fetchall()

    today = datetime.now(timezone.utc).date()
    buckets: dict[str, dict] = {}
    year, month = today.year, today.month
    for _ in range(months):
        key = f"{year:04d}-{month:02d}"
        buckets[key] = {"month": key, "revenue": Decimal("0"), "expenses": Decimal("0")}
        month -= 1
        if month == 0:
            month = 12
            year -= 1

    for date_str, raw_amount in rows:
        key = (date_str or "")[:7]
        bucket = buckets.get(key)
        if bucket is None:
            continue
        amount = Decimal(str(raw_amount))
        if amount > 0:
            bucket["revenue"] += amount
        else:
            bucket["expenses"] += -amount

    return sorted(buckets.values(), key=lambda b: b["month"])


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
        amount=_to_money(data["amount"]),
        date=data["date"],
        payment_type=data.get("payment_type"),
    )
    db.add(entry)
    db.commit()
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
# Manual update / delete by ID (PUT/DELETE /finance/entries/{id})
# ---------------------------------------------------------------------------
# Used by manual inline edit/delete (RecentActivityTable, AddTransactionModal
# edit mode) and by the frontend's delayed-API-execution Undo pattern for
# both manual and NLP-triggered deletes/edits.
# ---------------------------------------------------------------------------

def update_entry(user_id: int, entry_id: int, data: dict, db: Session) -> dict:
    """
    Updates a FinanceEntry by ID, scoped to user_id. Only fields present (and
    non-None) in `data` are applied — a partial patch.

    Raises:
        EntryNotFoundError — entry does not exist or is not owned by user_id.
    """
    from app.models import FinanceEntry

    entry = (
        db.query(FinanceEntry)
        .filter(FinanceEntry.id == entry_id, FinanceEntry.user_id == user_id)
        .first()
    )
    if entry is None:
        raise EntryNotFoundError(f"No transaction found with id={entry_id}.")

    for field in ("purchased", "categorization", "amount", "date", "payment_type"):
        if field in data and data[field] is not None:
            value = _to_money(data[field]) if field == "amount" else data[field]
            setattr(entry, field, value)

    db.commit()
    logger.info("Manually updated finance entry id=%s for user_id=%s", entry.id, user_id)

    return {
        "id": entry.id,
        "item": entry.purchased,
        "amount": entry.amount,
        "category": entry.categorization,
        "date": entry.date,
        "payment_type": entry.payment_type,
        "created_at": str(entry.created_at),
    }


def delete_entry(user_id: int, entry_id: int, db: Session) -> dict:
    """
    Deletes a FinanceEntry by ID, scoped to user_id.

    Raises:
        EntryNotFoundError — entry does not exist or is not owned by user_id.
    """
    from app.models import FinanceEntry

    entry = (
        db.query(FinanceEntry)
        .filter(FinanceEntry.id == entry_id, FinanceEntry.user_id == user_id)
        .first()
    )
    if entry is None:
        raise EntryNotFoundError(f"No transaction found with id={entry_id}.")

    snapshot = {
        "id": entry.id,
        "item": entry.purchased,
        "amount": entry.amount,
        "category": entry.categorization,
        "date": entry.date,
        "payment_type": entry.payment_type,
    }
    db.delete(entry)
    db.commit()
    logger.info("Manually deleted finance entry id=%s for user_id=%s", entry_id, user_id)
    return snapshot


# ---------------------------------------------------------------------------
# NLP mutation services (ADD / EDIT / DELETE via /finance/chat)
# ---------------------------------------------------------------------------
# These are the only code paths where an LLM-extracted intent is allowed to
# touch the database (Section 3 / 6.3 of the feature plan). Every one of them:
#   - Sources user_id from the JWT-authenticated caller — never from the LLM.
#   - Uses parameterised SQLAlchemy ORM calls, never string-built SQL.
#   - Scopes every read/write with FinanceEntry.user_id == user_id.
#   - Writes an audit_logs row after any successful mutation (Decision 4).
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _resolve_date(date_str: str) -> str:
    """Resolves the LLM's "today" sentinel, or validates an explicit YYYY-MM-DD date."""
    cleaned = date_str.strip()
    if cleaned.lower() == "today":
        return datetime.now(timezone.utc).date().isoformat()
    if not _DATE_RE.match(cleaned):
        raise ValueError(f"Invalid date '{date_str}'; expected YYYY-MM-DD or 'today'.")
    return cleaned


def _entry_snapshot(entry) -> dict:
    """JSON-serialisable snapshot of a FinanceEntry for audit_logs previous/new_state."""
    return {
        "id": entry.id,
        "purchased": entry.purchased,
        "categorization": entry.categorization,
        "amount": str(entry.amount),
        "date": entry.date,
        "payment_type": entry.payment_type,
    }


def _write_audit_log(
    db: Session,
    *,
    user_id: int,
    entry_id: Optional[int],
    action: str,
    previous_state: Optional[dict],
    new_state: Optional[dict],
    prompt: str,
) -> None:
    from app.models import AuditLog

    db.add(AuditLog(
        user_id=user_id,
        entry_id=entry_id,
        action=action,
        previous_state=previous_state,
        new_state=new_state,
        prompt=prompt,
    ))
    db.commit()


def create_entry_from_nlp(user_id: int, intent_data, prompt: str, db: Session) -> dict:
    """
    Creates a FinanceEntry from an LLM-extracted IntentAdd.

    Resolves the "today" date sentinel, applies the expense/income sign
    convention (expense = negative, income = positive), delegates the actual
    insert to create_entry() (no new DB code needed), then writes an
    audit_logs row for the successful mutation.
    """
    resolved_date = _resolve_date(intent_data.date)
    signed_amount = (
        -abs(intent_data.amount) if intent_data.type == "expense" else abs(intent_data.amount)
    )

    entry = create_entry(
        user_id=user_id,
        data={
            "purchased": intent_data.purchased,
            "categorization": intent_data.categorization,
            "amount": signed_amount,
            "date": resolved_date,
            "payment_type": intent_data.payment_type,
        },
        db=db,
    )

    _write_audit_log(
        db,
        user_id=user_id,
        entry_id=entry["id"],
        action="NLP_ADD",
        previous_state=None,
        new_state={**entry, "amount": str(entry["amount"])},
        prompt=prompt,
    )

    return entry


def resolve_target_entry(
    user_id: int,
    target_id: Optional[int],
    target_description: Optional[str],
    db: Session,
):
    """
    Resolves an EDIT/DELETE target to a FinanceEntry, ownership-checked.

    - If target_id is given: exact lookup scoped to user_id. This IS the
      ownership security check — an entry belonging to another user raises
      EntryNotFoundError exactly like a nonexistent ID (no distinguishable
      error that would leak whether the ID exists for someone else).
    - Otherwise: fuzzy ILIKE search on `purchased`, scoped to user_id, newest
      first, capped at 5. Returns the single match directly, or a list of
      candidates when more than one entry matches (disambiguation required).

    Returns:
        A single FinanceEntry ORM object, or a list[FinanceEntry] (len >= 2)
        when the caller must disambiguate.

    Raises:
        EntryNotFoundError — no matching entry found at all.
    """
    from app.models import FinanceEntry

    if target_id is not None:
        entry = (
            db.query(FinanceEntry)
            .filter(FinanceEntry.id == target_id, FinanceEntry.user_id == user_id)
            .first()
        )
        if entry is None:
            raise EntryNotFoundError(f"No transaction found with id={target_id}.")
        return entry

    term = (target_description or "").strip()
    if not term:
        raise EntryNotFoundError("No target specified to identify the transaction.")

    candidates = (
        db.query(FinanceEntry)
        .filter(FinanceEntry.user_id == user_id, FinanceEntry.purchased.ilike(f"%{term}%"))
        .order_by(FinanceEntry.id.desc())
        .limit(5)
        .all()
    )

    if not candidates:
        raise EntryNotFoundError(f"No transaction found matching '{term}'.")
    if len(candidates) == 1:
        return candidates[0]
    return candidates


def update_entry_from_nlp(user_id: int, intent_data, prompt: str, db: Session) -> dict:
    """
    Applies an LLM-extracted IntentEdit patch to the resolved target entry.

    Returns {"requires_confirmation": True, "candidates": [...]} without
    touching the database when target_description matched multiple entries.
    Otherwise applies the patch, commits, and writes an audit_logs row.
    """
    result = resolve_target_entry(user_id, intent_data.target_id, intent_data.target_description, db)

    if isinstance(result, list):
        return {
            "requires_confirmation": True,
            "candidates": [_entry_snapshot(e) for e in result],
        }

    entry = result

    # Defense-in-depth: patch keys are already allowlisted by IntentEdit's
    # Pydantic validator, but this is the last line of defense before a DB
    # write, so re-check here too (Section 6.6 risk table).
    disallowed = set(intent_data.patch.keys()) - EDITABLE_FIELDS
    if disallowed:
        raise ValueError(f"Patch contains disallowed fields: {sorted(disallowed)}")

    previous_state = _entry_snapshot(entry)

    for field, value in intent_data.patch.items():
        if field == "date":
            value = _resolve_date(str(value))
        elif field == "amount":
            value = _to_money(value)
        setattr(entry, field, value)

    db.commit()

    new_state = _entry_snapshot(entry)

    _write_audit_log(
        db,
        user_id=user_id,
        entry_id=entry.id,
        action="NLP_EDIT",
        previous_state=previous_state,
        new_state=new_state,
        prompt=prompt,
    )

    logger.info("NLP edit applied to entry id=%s for user_id=%s", entry.id, user_id)
    return {
        "requires_confirmation": False,
        "candidates": None,
        "data": new_state,
        "previous_state": previous_state,
    }


def delete_entry_from_nlp(user_id: int, intent_data, prompt: str, db: Session) -> dict:
    """
    Deletes the resolved target entry.

    Returns {"requires_confirmation": True, "candidates": [...]} without
    deleting anything when target_description matched multiple entries
    (Decision 1 — never mass-delete on an ambiguous match). Otherwise deletes
    the single resolved entry and writes an audit_logs row.
    """
    result = resolve_target_entry(user_id, intent_data.target_id, intent_data.target_description, db)

    if isinstance(result, list):
        return {
            "requires_confirmation": True,
            "candidates": [_entry_snapshot(e) for e in result],
        }

    entry = result
    previous_state = _entry_snapshot(entry)

    db.delete(entry)
    db.commit()

    _write_audit_log(
        db,
        user_id=user_id,
        entry_id=previous_state["id"],
        action="NLP_DELETE",
        previous_state=previous_state,
        new_state=None,
        prompt=prompt,
    )

    logger.info("NLP delete applied to entry id=%s for user_id=%s", previous_state["id"], user_id)
    return {"requires_confirmation": False, "candidates": None, "data": previous_state}


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
