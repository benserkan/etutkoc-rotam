"""Kredi ek paketi (Faz 3) — satın alınan kredi kovası.

credit_accounts.purchased_credits (2026-08-04):
  Tek seferlik iyzico kredi paketi satın alımları bu AYRI kovaya yazılır.
  bonus_credits'ten farkı: satın alınan kredi ay sonunda YANMAZ — yeni dönem
  hesabı açılırken kullanılmayan kısım devreder (kullanım önce tahsisat+bonus
  havuzundan, en son satın alınandan düşmüş sayılır).

Additive — mevcut satırlar 0 ile başlar (davranış değişmez).

Revision ID: i9j2m5o6o99i
Revises: h8i1l4n5n88h
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "i9j2m5o6o99i"
down_revision = "h8i1l4n5n88h"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "credit_accounts",
        sa.Column(
            "purchased_credits", sa.Integer(), nullable=False, server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("credit_accounts", "purchased_credits")
