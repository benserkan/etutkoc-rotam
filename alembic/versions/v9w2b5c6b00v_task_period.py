"""M6 — Görev periyodu (sabah/öğle/akşam) opsiyonel alan.

Yeni alan: tasks.period (String, nullable)
  - Değerler: "morning" | "noon" | "evening" | NULL
  - NULL = period atanmamış (eski davranış: tek liste)
  - En az 1 görev period dolu ise öğrenci görünümünde 3 başlıklı (Sabah/Öğle/
    Akşam) bölüm; period=NULL görevler "Saatsiz" altında.
  - scheduled_hour'dan BAĞIMSIZ — koç açık seçer (her zaman opsiyonel).

Additive + downgrade'li, mevcut veriyi etkilemez.
"""
from alembic import op
import sqlalchemy as sa


revision = "v9w2b5c6b00v"
down_revision = "u8v1z3a4z22t"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("period", sa.String(length=16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("period")
