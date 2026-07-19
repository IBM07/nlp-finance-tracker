"""add audit_logs table

Revision ID: 0002_audit_logs
Revises: 0001_initial
Create Date: 2026-07-16

Creates:
  - audit_logs table — append-only paper trail for every NLP-triggered
    mutation (NLP_ADD / NLP_EDIT / NLP_DELETE).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "0002_audit_logs"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("entry_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("previous_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=True),
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
        op.f("ix_audit_logs_user_id"),
        "audit_logs",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_user_id"), table_name="audit_logs")
    op.drop_table("audit_logs")
