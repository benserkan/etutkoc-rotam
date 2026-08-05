"""Hedef Havuzu — Instagram kullanıcı adı alanı (2026-08-05).

sales_prospects.instagram: Instagram'dan keşfedilen bireysel koçların kimliği.
Telefon tekilleştirmenin yanında "bu hesabı zaten eklemiş miyim?" sorusunu da
yanıtlar (mobil hızlı ekleme akışı).

Additive — mevcut satırlar NULL.

Revision ID: k1l4o7q8q11k
Revises: j0k3n6p7p00j
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "k1l4o7q8q11k"
down_revision = "j0k3n6p7p00j"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales_prospects",
        sa.Column("instagram", sa.String(length=80), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sales_prospects", "instagram")
