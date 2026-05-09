"""usage_events + credit_accounts + users.plan

Revision ID: x6s2v5u6v55p
Revises: w5r1u4t5u44o
Create Date: 2026-05-09 22:00:00.000000

Stage 6 — kullanım ölçümü + kredi sistemi:
- Tablo: usage_events (append-only event log)
- Tablo: credit_accounts (sahip+period başına 1 satır, UNIQUE)
- users.plan (varsayılan 'free' — bağımsız öğretmenler için)

Polymorphic owner: owner_type='institution' | 'user'
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "x6s2v5u6v55p"
down_revision: Union[str, None] = "w5r1u4t5u44o"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) users.plan kolonu — varsayılan 'free'
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column(
            "plan", sa.String(length=32), nullable=False,
            server_default=sa.text("'free'"),
        ))

    # 2) usage_events — append-only event log
    op.create_table(
        "usage_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_type", sa.String(length=20), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("period_year_month", sa.String(length=7), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("usage_events") as batch:
        batch.create_index(
            "ix_usage_events_owner_time",
            ["owner_type", "owner_id", "occurred_at"],
        )
        batch.create_index(
            "ix_usage_events_owner_period",
            ["owner_type", "owner_id", "period_year_month"],
        )
        batch.create_index(
            "ix_usage_events_period_year_month",
            ["period_year_month"],
        )
        batch.create_index(
            "ix_usage_events_occurred_at",
            ["occurred_at"],
        )

    # 3) credit_accounts — aylık snapshot
    op.create_table(
        "credit_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_type", sa.String(length=20), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("period_year_month", sa.String(length=7), nullable=False),
        sa.Column("allocated_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("used_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bonus_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("plan_code", sa.String(length=32), nullable=False, server_default="free"),
        sa.Column("warn_80_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "hard_block_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0"),
        ),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_type", "owner_id", "period_year_month",
            name="uq_credit_account_owner_period",
        ),
    )
    with op.batch_alter_table("credit_accounts") as batch:
        batch.create_index("ix_credit_accounts_owner_type", ["owner_type"])
        batch.create_index("ix_credit_accounts_owner_id", ["owner_id"])


def downgrade() -> None:
    op.drop_table("credit_accounts")
    op.drop_table("usage_events")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("plan")
