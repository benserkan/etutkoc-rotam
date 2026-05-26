"""TaskRequest: task_title_snapshot + task_date_snapshot (REMOVE audit izi)

Revision ID: o2p5t7u8t77n
Revises: n1o4s6t7s66m
Create Date: 2026-05-26

n1o4s6t7s66m'de task_id FK CASCADE -> SET NULL yapıldı (task silinse de request
kalsın diye). Ama task_id NULL olunca detail sayfasında "Mevcut görev: yok"
görünüyor — koç hangi görevi onayladığını GÖRMÜYOR.

Çözüm: _apply_remove silmeden ÖNCE task.title + task.date'i request'e snapshot'lar.
Detail sayfası task yoksa snapshot'tan gösterir. Eski request'ler için
(snapshot eklenmeden önce silinmiş) snapshot NULL kalır — geri yüklenemez.
"""
from alembic import op
import sqlalchemy as sa


revision = "o2p5t7u8t77n"
down_revision = "n1o4s6t7s66m"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "task_requests",
        sa.Column("task_title_snapshot", sa.String(200), nullable=True),
    )
    op.add_column(
        "task_requests",
        sa.Column("task_date_snapshot", sa.Date, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("task_requests", "task_date_snapshot")
    op.drop_column("task_requests", "task_title_snapshot")
