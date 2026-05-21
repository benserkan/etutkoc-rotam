"""Offers tablosu (Sprint D.1 — Bireysel Teklif Sistemi).

Revision ID: f0c3e5d6e55x
Revises: e9b2d4c5d44w
Create Date: 2026-05-16 15:30:00.000000

Yeni tablo:
  - offers: kurum bazlı özel teklifler (indirim, deneme uzatma, plan yükseltme,
    onboarding saati, vb.). Token bazlı public link ile gönderilir.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f0c3e5d6e55x"
down_revision: Union[str, None] = "e9b2d4c5d44w"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "offers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "institution_id", sa.Integer(),
            sa.ForeignKey("institutions.id", ondelete="CASCADE",
                          name="fk_offers_institution"),
            nullable=False,
        ),
        sa.Column("token", sa.String(length=64), nullable=False, unique=True),
        sa.Column(
            "kind",
            sa.Enum(
                "discount_percent", "discount_fixed", "trial_extension",
                "plan_upgrade", "free_feature", "onboarding_hours", "custom",
                name="offerkind",
            ),
            nullable=False,
        ),
        sa.Column("value", sa.Numeric(10, 2), nullable=True),
        sa.Column("value_unit", sa.String(length=16), nullable=True),
        sa.Column("duration_months", sa.Integer(), nullable=True),
        sa.Column("new_plan", sa.String(length=32), nullable=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("public_message", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft", "sent", "accepted", "declined",
                "expired", "cancelled",
                name="offerstatus",
            ),
            nullable=False, server_default="draft",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decline_reason", sa.String(length=500), nullable=True),
        sa.Column(
            "plan_change_history_id", sa.Integer(),
            sa.ForeignKey("plan_change_history.id", ondelete="SET NULL",
                          name="fk_offers_plan_change"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL",
                          name="fk_offers_created_by"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_offers_institution_id", "offers", ["institution_id"])
    op.create_index("ix_offers_institution_status", "offers",
                    ["institution_id", "status"])
    op.create_index("ix_offers_token", "offers", ["token"], unique=True)
    op.create_index("ix_offers_status_expires", "offers",
                    ["status", "expires_at"])


def downgrade() -> None:
    op.drop_index("ix_offers_status_expires", table_name="offers")
    op.drop_index("ix_offers_token", table_name="offers")
    op.drop_index("ix_offers_institution_status", table_name="offers")
    op.drop_index("ix_offers_institution_id", table_name="offers")
    op.drop_table("offers")
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        sa.Enum(name="offerkind").drop(bind, checkfirst=True)
        sa.Enum(name="offerstatus").drop(bind, checkfirst=True)
