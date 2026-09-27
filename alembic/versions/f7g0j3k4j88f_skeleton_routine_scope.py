"""Haftalık İskelet — rutin kapsamı + satırın ikinci kaynağı (F2-4)

Revision ID: f7g0j3k4j88f
Revises: e6f9i2j3i77e
Create Date: 2026-09-27

Koç açıklaması (Zeynep Ela · TYT Matematik): rutin yalnız PROBLEMLER (Oran-
Orantı + problem konuları + Problem Denemeleri); kitabın geri kalanı konu
hattıdır. Rutin kitaba bağlı "kaldığı yerden sırayla" ilerleyince Fonksiyon/
Polinomlar gibi konu hattı bölümlerine kayıyordu. Konu hattında ise her ders
iki ana kaynakla yürür: bir konu 1. kaynakta bitince koç ya 2. kaynaktan aynı
konuyu ya 1. kaynakta sıradaki konuyu seçer.

- weekly_skeleton_slots + routine_scope (VARCHAR(16), nullable):
  'book' = kitabın tamamı (paragraf, geometri) · 'problems' = yalnız problem
  bölümleri; kaynak bitince sıradaki kaynağın problemlerinden baştan döner.
  NULL = 'book' (mevcut davranış korunur).
- weekly_skeleton_slots + second_book_id (INTEGER, nullable, FK books SET NULL):
  konu satırının 2. ana kaynağı; 1. kaynakta konu bitince seçenek olarak sunulur.
Additive, mevcut satırlar etkilenmez, downgrade'li.
"""
from alembic import op
import sqlalchemy as sa

revision = "f7g0j3k4j88f"
down_revision = "e6f9i2j3i77e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("weekly_skeleton_slots") as b:
        b.add_column(sa.Column("routine_scope", sa.String(length=16), nullable=True))
        b.add_column(sa.Column("second_book_id", sa.Integer(), nullable=True))
        b.create_foreign_key(
            "fk_weekly_skeleton_slots_second_book_id", "books",
            ["second_book_id"], ["id"], ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("weekly_skeleton_slots") as b:
        b.drop_constraint("fk_weekly_skeleton_slots_second_book_id", type_="foreignkey")
        b.drop_column("second_book_id")
        b.drop_column("routine_scope")
