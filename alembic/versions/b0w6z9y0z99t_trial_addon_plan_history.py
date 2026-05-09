"""User+Institution trial alanları, plan_change_history, addons

Revision ID: b0w6z9y0z99t
Revises: a9v5y8x9y88s
Create Date: 2026-05-10 00:30:00.000000

Stage 9 (Faz 2) — Plan/üyelik altyapısı:
- users.trial_ends_at + post_trial_plan
- institutions.trial_ends_at + post_trial_plan + subscription_kind +
  subscription_period_end + subscription_pause_until + performance_guarantee +
  guarantee_extended_at
- plan_change_history tablosu
- addons tablosu (WhatsApp Veli, AI Plus, Veli Portalı)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b0w6z9y0z99t"
down_revision: Union[str, None] = "a9v5y8x9y88s"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) users tablosuna trial alanları
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column(
            "trial_ends_at", sa.DateTime(timezone=True), nullable=True,
        ))
        batch.add_column(sa.Column(
            "post_trial_plan", sa.String(length=32), nullable=True,
        ))

    # 2) institutions tablosuna trial + abonelik + garanti alanları
    with op.batch_alter_table("institutions") as batch:
        batch.add_column(sa.Column(
            "trial_ends_at", sa.DateTime(timezone=True), nullable=True,
        ))
        batch.add_column(sa.Column(
            "post_trial_plan", sa.String(length=32), nullable=True,
        ))
        batch.add_column(sa.Column(
            "subscription_kind", sa.String(length=20), nullable=False,
            server_default="monthly",
        ))
        batch.add_column(sa.Column(
            "subscription_period_end", sa.DateTime(timezone=True), nullable=True,
        ))
        batch.add_column(sa.Column(
            "subscription_pause_until", sa.DateTime(timezone=True), nullable=True,
        ))
        batch.add_column(sa.Column(
            "performance_guarantee", sa.Boolean(), nullable=False,
            server_default=sa.text("0"),
        ))
        batch.add_column(sa.Column(
            "guarantee_extended_at", sa.DateTime(timezone=True), nullable=True,
        ))

    # 3) plan_change_history
    op.create_table(
        "plan_change_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_type", sa.String(length=20), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("from_plan", sa.String(length=32), nullable=True),
        sa.Column("to_plan", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], ondelete="SET NULL",
            name="fk_pch_actor",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("plan_change_history") as batch:
        batch.create_index("ix_pch_owner", ["owner_type", "owner_id"])
        batch.create_index("ix_pch_occurred", ["occurred_at"])

    # 4) addons
    op.create_table(
        "addons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_type", sa.String(length=20), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("addon_kind", sa.String(length=32), nullable=False),
        sa.Column(
            "period_start", sa.DateTime(timezone=True), nullable=False,
        ),
        sa.Column(
            "period_end", sa.DateTime(timezone=True), nullable=False,
        ),
        sa.Column(
            "auto_renew", sa.Boolean(), nullable=False, server_default=sa.text("1"),
        ),
        sa.Column(
            "cancelled_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column("cancelled_by_user_id", sa.Integer(), nullable=True),
        sa.Column("price_try", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["cancelled_by_user_id"], ["users.id"], ondelete="SET NULL",
            name="fk_addon_cancelled_by",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_type", "owner_id", "addon_kind", "period_start",
            name="uq_addon_owner_kind_period",
        ),
    )
    with op.batch_alter_table("addons") as batch:
        batch.create_index("ix_addons_owner", ["owner_type", "owner_id"])


def downgrade() -> None:
    op.drop_table("addons")
    op.drop_table("plan_change_history")
    with op.batch_alter_table("institutions") as batch:
        batch.drop_column("guarantee_extended_at")
        batch.drop_column("performance_guarantee")
        batch.drop_column("subscription_pause_until")
        batch.drop_column("subscription_period_end")
        batch.drop_column("subscription_kind")
        batch.drop_column("post_trial_plan")
        batch.drop_column("trial_ends_at")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("post_trial_plan")
        batch.drop_column("trial_ends_at")
