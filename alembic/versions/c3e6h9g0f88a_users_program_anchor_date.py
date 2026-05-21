"""users.program_anchor_date — öğrencinin hafta bloğu anchor'ı

Revision ID: c3e6h9g0f88a
Revises: b2d5g8f9e77z
Create Date: 2026-05-17 14:00:00.000000

Öğrenciye özel "hafta başı" tarihini saklar. NULL = eski davranış
(en eski Task.date'i fallback). Set ise haftalık view bu tarihi anchor sayar
ve pencereyi `anchor + N*7` günlerden oluşan bloğa yerleştirir.
Koçluk günü değişirse öğretmen UI'dan bu alanı yeniden ayarlar.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3e6h9g0f88a"
down_revision: Union[str, None] = "b2d5g8f9e77z"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("program_anchor_date", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("program_anchor_date")
