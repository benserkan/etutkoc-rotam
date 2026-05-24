"""Veri düzeltme — geçersiz tasktype 'study' → 'OTHER'

Revision ID: l9m2p4q5p33j
Revises: k8l1o3p4o22i
Create Date: 2026-05-24 18:30:00.000000

Kopuk-cron denetimi sırasında ortaya çıktı: tasks tablosunda eski/küçük harf
'study' değeri kalmış (geçerli tasktype enum'unda yok: TEST/VIDEO/OZET/.../OTHER).
Bu satırları yükleyen kod (cron'lar dahil) LookupError atıyordu. Geçersiz değer
'OTHER' (etkinlik görevi) olarak normalize edilir — satırlar KORUNUR (silinmez).

İdempotent (eşleşen satır yoksa no-op). Downgrade no-op (orijinal 'study'
ayrımı geri getirilemez; veri kaybı önlemek için OTHER kalır).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l9m2p4q5p33j"
down_revision: Union[str, None] = "k8l1o3p4o22i"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE tasks SET type = 'OTHER' WHERE type = 'study'"))


def downgrade() -> None:
    # Geri alma yok — hangi OTHER'ın eskiden 'study' olduğu bilinemez (veri kaybı önlemi).
    pass
