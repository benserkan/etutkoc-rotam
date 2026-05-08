"""parent phone verifications — WA OTP doğrulama tablosu

Revision ID: f8a4d5b6c707
Revises: e7b3c4d5f606
Create Date: 2026-05-02 10:00:00.000000

Sprint 6 — WhatsApp Cloud API entegrasyonu için telefon doğrulama:
- parent_phone_verifications tablosu: parent_id, phone, code, attempts,
  expires_at, consumed_at
- Veli settings'te WA aç → kod gönder → kod gir → consumed_at + pref güncellenir
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f8a4d5b6c707"
down_revision: Union[str, None] = "e7b3c4d5f606"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "parent_phone_verifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["parent_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ppv_parent_created",
        "parent_phone_verifications",
        ["parent_id", "created_at"],
    )
    op.create_index("ix_ppv_phone", "parent_phone_verifications", ["phone"])


def downgrade() -> None:
    op.drop_index("ix_ppv_phone", table_name="parent_phone_verifications")
    op.drop_index("ix_ppv_parent_created", table_name="parent_phone_verifications")
    op.drop_table("parent_phone_verifications")
