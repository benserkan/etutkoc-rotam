"""Hedef Havuzu — telefon opsiyonel (Instagram-only aday) (2026-08-05).

Saha bulgusu: bireysel öğrenci koçlarının çoğu Instagram'da telefon
YAYIMLAMIYOR (aday müşteriyi DM'de karşılamak istiyorlar). İlk temas kanalı
DM olunca aday, telefonu olmadan da havuza girebilmeli — kimlik `instagram`
alanıdır. Telefon sonradan (kişi dönüş yapınca) doldurulur.

Kural: telefon VEYA instagram'dan en az biri zorunlu (servis katmanında).

Revision ID: l2m5p8r9r22l
Revises: k1l4o7q8q11k
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "l2m5p8r9r22l"
down_revision = "k1l4o7q8q11k"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sales_prospects") as b:
        b.alter_column("phone", existing_type=sa.String(length=32), nullable=True)


def downgrade() -> None:
    # Geri alırken telefonsuz satırlar engel olur — boşları placeholder yapmak
    # veri bozar; bu yüzden downgrade yalnız kısıtı geri koyar (temiz veri şart).
    with op.batch_alter_table("sales_prospects") as b:
        b.alter_column("phone", existing_type=sa.String(length=32), nullable=False)
