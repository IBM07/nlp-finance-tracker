# ==========================================
# tests/test_sql_guard.py
# ==========================================
# Priority tests for the sql_guard module.
# These MUST pass before any release — they verify that malicious
# LLM output is blocked before it reaches the database.
# ==========================================

import pytest
from app.finance.sql_guard import validate_sql, SQLGuardError


# ---------------------------------------------------------------------------
# Happy path — valid SELECT queries
# ---------------------------------------------------------------------------

class TestValidQueries:
    def test_simple_select(self):
        sql = "SELECT * FROM finance_entries WHERE user_id = 1"
        assert validate_sql(sql) == sql

    def test_select_with_aggregation(self):
        sql = (
            "SELECT categorization, SUM(amount) AS total "
            "FROM finance_entries WHERE user_id = 1 "
            "GROUP BY categorization ORDER BY total DESC"
        )
        assert validate_sql(sql) == sql

    def test_select_with_limit(self):
        sql = "SELECT id, purchased, amount FROM finance_entries WHERE user_id = 42 LIMIT 10"
        assert validate_sql(sql) == sql

    def test_select_with_date_filter(self):
        sql = (
            "SELECT * FROM finance_entries "
            "WHERE user_id = 1 AND date >= '2025-01-01'"
        )
        assert validate_sql(sql) == sql


# ---------------------------------------------------------------------------
# Blocked: banned statement types
# ---------------------------------------------------------------------------

class TestBannedStatements:
    def test_drop_table(self):
        with pytest.raises(SQLGuardError, match="Only SELECT statements are permitted"):
            validate_sql("DROP TABLE finance_entries")

    def test_delete(self):
        with pytest.raises(SQLGuardError):
            validate_sql("DELETE FROM finance_entries WHERE user_id = 1")

    def test_insert(self):
        with pytest.raises(SQLGuardError):
            validate_sql("INSERT INTO finance_entries (purchased) VALUES ('hack')")

    def test_update(self):
        with pytest.raises(SQLGuardError):
            validate_sql("UPDATE finance_entries SET amount = 0 WHERE user_id = 1")

    def test_truncate(self):
        with pytest.raises(SQLGuardError):
            validate_sql("TRUNCATE TABLE finance_entries")

    def test_alter(self):
        with pytest.raises(SQLGuardError):
            validate_sql("ALTER TABLE finance_entries ADD COLUMN evil TEXT")

    def test_create(self):
        with pytest.raises(SQLGuardError):
            validate_sql("CREATE TABLE evil (id INT)")


# ---------------------------------------------------------------------------
# Blocked: statement chaining via semicolons
# ---------------------------------------------------------------------------

class TestStatementChaining:
    def test_semicolon_chaining(self):
        with pytest.raises(SQLGuardError, match="Multi-statement"):
            validate_sql(
                "SELECT * FROM finance_entries WHERE user_id = 1; DROP TABLE users"
            )

    def test_double_semicolon(self):
        with pytest.raises(SQLGuardError):
            validate_sql(
                "SELECT 1;; DROP TABLE finance_entries"
            )


# ---------------------------------------------------------------------------
# Blocked: comment injection
# ---------------------------------------------------------------------------

class TestCommentInjection:
    def test_line_comment(self):
        with pytest.raises(SQLGuardError, match="comments"):
            validate_sql("SELECT * FROM finance_entries WHERE user_id = 1 -- injected")

    def test_block_comment_open(self):
        with pytest.raises(SQLGuardError, match="comments"):
            validate_sql("SELECT /* injected */ * FROM finance_entries WHERE user_id = 1")

    def test_hash_comment(self):
        with pytest.raises(SQLGuardError, match="comments"):
            validate_sql("SELECT * FROM finance_entries # comment")


# ---------------------------------------------------------------------------
# Blocked: unknown tables
# ---------------------------------------------------------------------------

class TestTableWhitelist:
    def test_unknown_table(self):
        with pytest.raises(SQLGuardError, match="not permitted"):
            validate_sql("SELECT * FROM users WHERE id = 1")

    def test_system_table(self):
        with pytest.raises(SQLGuardError):
            validate_sql("SELECT * FROM information_schema.tables")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_string(self):
        with pytest.raises(SQLGuardError, match="Empty"):
            validate_sql("")

    def test_whitespace_only(self):
        with pytest.raises(SQLGuardError, match="Empty"):
            validate_sql("   ")

    def test_none_input(self):
        with pytest.raises(SQLGuardError, match="Empty"):
            validate_sql(None)  # type: ignore
