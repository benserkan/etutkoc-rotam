"""task_requests.task_items_snapshot — talep anındaki görev kalemleri (2026-09-05)

SAHA HATASI: REPLACE ("Kaynağı değiştir") talebi onaylanınca `_apply_replace`
eski kalemleri siler ve başlığı yeniden yazar. Detay sayfasındaki "Mevcut görev"
bloğu CANLI görevden okuduğu için onay sonrası ÖNERİLENLE AYNI görünüyordu →
koç "neyi onayladım, öğrenci neyi değiştirmek istemişti" sorusunu yanıtlayamıyordu.

Additive + nullable. Onay/red anında (uygulamadan ÖNCE) doldurulur; eski
taleplerde NULL kalır ve UI canlı göreve düşer (geriye uyum).

Revision ID: u6v9y2z3y77u
Revises: t5u8x1y2x66t
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "u6v9y2z3y77u"
down_revision = "t5u8x1y2x66t"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "task_requests",
        sa.Column("task_items_snapshot", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("task_requests", "task_items_snapshot")
