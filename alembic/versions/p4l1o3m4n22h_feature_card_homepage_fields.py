"""feature_cards — anasayfa kart yapısına hizalama

Revision ID: p4l1o3m4n22h
Revises: o3k0n2l3m11g
Create Date: 2026-05-14 18:00:00.000000

Anasayfa kartının 7 parçasının admin form alanlarıyla bire bir eşleşmesi
için 3 yeni kolon + 1 genişletme:

- category_icon (str, 16) — emoji/karakter (örn. "📅", "🧠", "⚠️")
- category_label (str, 64) — UPPERCASE rozet metni (örn. "Günlük Rota")
- demo_duration_label (str, 64 nullable) — "2 dk · 8 sahne" gibi süre etiketi
- tagline 240 → 400 char (anasayfa açıklama paragrafı için <strong> destekli)

Bu kolonlar Katman 2'de anasayfa render'ına bağlanacak — şu an boş kalır,
seed script ile mevcut 9 kart için doldurulur.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p4l1o3m4n22h"
down_revision: Union[str, None] = "o3k0n2l3m11g"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("feature_cards") as batch:
        batch.add_column(
            sa.Column("category_icon", sa.String(length=16), nullable=False, server_default="✨"),
        )
        batch.add_column(
            sa.Column("category_label", sa.String(length=64), nullable=False, server_default=""),
        )
        batch.add_column(
            sa.Column("demo_duration_label", sa.String(length=64), nullable=True),
        )
        # tagline 240 → 400 (anasayfa açıklama paragrafı için yer)
        batch.alter_column(
            "tagline",
            existing_type=sa.String(length=240),
            type_=sa.String(length=400),
            existing_nullable=False,
            existing_server_default="",
        )


def downgrade() -> None:
    with op.batch_alter_table("feature_cards") as batch:
        batch.alter_column(
            "tagline",
            existing_type=sa.String(length=400),
            type_=sa.String(length=240),
            existing_nullable=False,
            existing_server_default="",
        )
        batch.drop_column("demo_duration_label")
        batch.drop_column("category_label")
        batch.drop_column("category_icon")
