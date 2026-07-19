# ==========================================
# models.py — SQLAlchemy ORM Models
# ==========================================
# Defines the two core tables:
#
#   User         — one row per registered account
#   FinanceEntry — one row per expense, always scoped to a user_id
#
# Key decisions:
#   - amount uses Numeric(10, 2) not REAL/Float — avoids floating-point
#     rounding errors with money (0.1 + 0.2 == 0.30000000000000004 in float).
#   - user_id foreign key on FinanceEntry is the critical multi-tenancy guard:
#     every query at the application layer MUST filter by user_id.
#   - Timestamps (created_at) use server_default=func.now() so the DB sets
#     them — not the app clock, which may differ across workers.
# ==========================================

from datetime import datetime
from decimal import Decimal
from typing import Any
from sqlalchemy import (
    Integer,
    String,
    Numeric,
    DateTime,
    ForeignKey,
    Text,
    func,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ---------------------------------------------------------------------------
# User model
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship — gives us user.entries to fetch all FinanceEntries
    entries: Mapped[list["FinanceEntry"]] = relationship(
        "FinanceEntry",
        back_populates="user",
        cascade="all, delete-orphan",   # deleting a User deletes all their entries
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"


# ---------------------------------------------------------------------------
# FinanceEntry model
# ---------------------------------------------------------------------------

class FinanceEntry(Base):
    __tablename__ = "finance_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ---- Multi-tenancy -------------------------------------------------------
    # Every entry MUST belong to a user. ON DELETE CASCADE means if the parent
    # User is deleted, their entries are cleaned up automatically at the DB level.
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,           # queries always filter by user_id — index is critical
    )

    # ---- Finance fields ------------------------------------------------------
    purchased: Mapped[str] = mapped_column(String(255), nullable=False)
    categorization: Mapped[str] = mapped_column(String(50), nullable=False)

    # Numeric(10, 2): up to 99,999,999.99 — exact decimal, no float rounding
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    payment_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ---- Relationship --------------------------------------------------------
    user: Mapped["User"] = relationship("User", back_populates="entries")

    def __repr__(self) -> str:
        return (
            f"<FinanceEntry id={self.id} user_id={self.user_id} "
            f"purchased={self.purchased!r} amount={self.amount}>"
        )


# ---------------------------------------------------------------------------
# Composite index — covers the most common query pattern:
#   SELECT ... FROM finance_entries WHERE user_id = ? AND date >= ?
# ---------------------------------------------------------------------------
Index("ix_finance_entries_user_date", FinanceEntry.user_id, FinanceEntry.date)


# ---------------------------------------------------------------------------
# AuditLog model
# ---------------------------------------------------------------------------
# Captures every AI-driven write operation (NLP_ADD / NLP_EDIT / NLP_DELETE)
# for debugging user complaints and as the foundation for a future
# "Transaction History" page. Never mutated after insert — append-only.
# ---------------------------------------------------------------------------

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The finance_entries row affected. No FK constraint — the row may already
    # be deleted (NLP_DELETE) by the time this log is read back.
    entry_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    action: Mapped[str] = mapped_column(String(20), nullable=False)  # NLP_ADD | NLP_EDIT | NLP_DELETE

    previous_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    new_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} user_id={self.user_id} action={self.action!r} entry_id={self.entry_id}>"
