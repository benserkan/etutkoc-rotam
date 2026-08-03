"""AI erişim anahtarları — koç/kurum müdahale mekanizması.

users tablosuna iki nullable damga (2026-08-03):
  ai_self_disabled_at   — kullanıcının kendi tetiklediği AI kapalı
                          (öğrencide koç kapatır; koçta kurum yöneticisi
                          kapatır → alt-ağacın tüm AI harcaması durur)
  ai_parent_disabled_at — yalnız öğrenci satırında: bu öğrencinin velileri
                          Rota AI kullanamaz

Additive — mevcut veri etkilenmez (NULL = açık, bugünkü davranış).

Revision ID: h8i1l4n5n88h
Revises: g7h0k3m4m77g
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "h8i1l4n5n88h"
down_revision = "g7h0k3m4m77g"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("ai_self_disabled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("ai_parent_disabled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "ai_parent_disabled_at")
    op.drop_column("users", "ai_self_disabled_at")
