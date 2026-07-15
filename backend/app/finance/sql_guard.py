# ==========================================
# finance/sql_guard.py — SQL Validation Layer
# ==========================================
# Ported from Phase 0's root-level sql_guard.py.
# Updated whitelist to match the new table name: finance_entries
# (the SQLAlchemy model uses __tablename__ = "finance_entries")
# ==========================================

import re
import logging
import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import Keyword, DML

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# WHITELIST — only these identifiers may appear in a valid query
# ---------------------------------------------------------------------------

ALLOWED_TABLES = {"finance_entries"}

ALLOWED_COLUMNS = {
    "id",
    "user_id",
    "purchased",
    "categorization",
    "amount",
    "date",
    "payment_type",
    "created_at",
}

# ---------------------------------------------------------------------------
# BANNED PATTERNS
# ---------------------------------------------------------------------------

_BANNED_KEYWORDS = [
    r"\bDROP\b",
    r"\bDELETE\b",
    r"\bUPDATE\b",
    r"\bINSERT\b",
    r"\bALTER\b",
    r"\bTRUNCATE\b",
    r"\bCREATE\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bEXEC\b",
    r"\bEXECUTE\b",
    r"\bXP_\w+",
    r"\bINTO\b",
    r"\bATTACH\b",
    r"\bDETACH\b",
    r"\bPRAGMA\b",
    r"\bLOAD_FILE\b",
    r"\bOUTFILE\b",
    r"\bDUMPFILE\b",
]

_BANNED_COMMENT_PATTERNS = [
    r"--",
    r"/\*",
    r"\*/",
    r"#",
]

_BANNED_RE = re.compile("|".join(_BANNED_KEYWORDS), flags=re.IGNORECASE)
_COMMENT_RE = re.compile("|".join(_BANNED_COMMENT_PATTERNS))


class SQLGuardError(ValueError):
    """Raised when validation fails. Message is safe to log."""
    pass


def validate_sql(sql: str) -> str:
    """
    Validates an LLM-generated SQL string.
    Returns the cleaned SQL if valid; raises SQLGuardError otherwise.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise SQLGuardError("Empty or non-string SQL input.")

    sql = sql.strip()

    # 1. No multi-statement chaining
    statements = [s for s in sqlparse.split(sql) if s.strip()]
    if len(statements) > 1:
        logger.warning("SQL guard blocked multi-statement input: %s", sql)
        raise SQLGuardError("Multi-statement SQL is not allowed.")

    # 2. No comment injection
    if _COMMENT_RE.search(sql):
        logger.warning("SQL guard blocked comment injection: %s", sql)
        raise SQLGuardError("SQL comments are not allowed.")

    # 3. Must be a SELECT
    parsed: Statement = sqlparse.parse(sql)[0]
    statement_type = parsed.get_type()

    if statement_type != "SELECT":
        logger.warning("SQL guard blocked non-SELECT (type=%s): %s", statement_type, sql)
        raise SQLGuardError(
            f"Only SELECT statements are permitted. Got: {statement_type or 'unknown'}"
        )

    # 4. Banned keyword regex scan
    match = _BANNED_RE.search(sql)
    if match:
        logger.warning("SQL guard blocked banned token '%s': %s", match.group(), sql)
        raise SQLGuardError(f"Banned keyword detected: '{match.group()}'")

    # 5. Table whitelist
    _check_table_whitelist(parsed, sql)

    logger.info("SQL guard: query passed all checks.")
    return sql


def _check_table_whitelist(parsed: Statement, original_sql: str) -> None:
    tokens = list(parsed.flatten())
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.ttype in (Keyword, DML) or tok.ttype is Keyword:
            val = tok.normalized.upper()
            if val in ("FROM", "JOIN", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "CROSS JOIN"):
                j = i + 1
                while j < len(tokens) and tokens[j].is_whitespace:
                    j += 1
                if j < len(tokens):
                    table_name = tokens[j].normalized.lower()
                    if table_name not in ALLOWED_TABLES:
                        logger.warning(
                            "SQL guard blocked unknown table '%s': %s", table_name, original_sql
                        )
                        raise SQLGuardError(
                            f"Access to table '{table_name}' is not permitted."
                        )
        i += 1
