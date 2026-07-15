"""initial schema: users and finance_entries

Revision ID: 0001_initial
Revises: 
Create Date: 2026-07-13

Creates:
  - users table
  - finance_entries table (with user_id FK, Numeric(10,2) amount)
  - composite index on (user_id, date) for common query pattern
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column(
            "hashed_password", sa.String(length=255), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # --- finance_entries ---
    op.create_table(
        "finance_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("purchased", sa.String(length=255), nullable=False),
        sa.Column("categorization", sa.String(length=50), nullable=False),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("date", sa.String(length=10), nullable=False),
        sa.Column("payment_type", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_finance_entries_user_id"),
        "finance_entries",
        ["user_id"],
        unique=False,
    )
    # Composite index for common query: WHERE user_id = ? AND date >= ?
    op.create_index(
        "ix_finance_entries_user_date",
        "finance_entries",
        ["user_id", "date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_finance_entries_user_date", table_name="finance_entries")
    op.drop_index(
        op.f("ix_finance_entries_user_id"), table_name="finance_entries"
    )
    op.drop_table("finance_entries")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
