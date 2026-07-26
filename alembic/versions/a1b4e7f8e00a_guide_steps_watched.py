"""Rehber izleme ilerlemesi sunucuda — user_guide_states.steps_watched

Kullanıcı bölüm İÇİNDE hangi adımları sonuna kadar izledi (bölüm anahtarı →
adım indeksleri JSON'u). Oturum düşse / cihaz değişse de rehber kaldığı
adımdan devam eder (2026-07-23 saha bulgusu: izleme ilerlemesi yalnız
tarayıcı state'indeydi, logout sonrası sıfırlanıyordu).

Additive — mevcut satırlar '{}' ile başlar. Downgrade'li.

Revision ID: a1b4e7f8e00a
Revises: z0a3d6e7d99z
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b4e7f8e00a"
down_revision = "z0a3d6e7d99z"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_guide_states",
        sa.Column("steps_watched", sa.Text(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("user_guide_states", "steps_watched")
