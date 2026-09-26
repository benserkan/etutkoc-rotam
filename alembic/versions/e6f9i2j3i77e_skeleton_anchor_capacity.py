"""Haftalık İskelet — çapa satırı + gün kapasitesi (F2-3)

Revision ID: e6f9i2j3i77e
Revises: d5e8h1i2h66d
Create Date: 2026-09-26

Koç açıklaması (Taha 12. sınıf okul+kurs · Zeynep Ela mezun+dershane): günün
~1/4'ü okulda/dershanede İŞLENEN DERS (sabit gün — "çapa"), ~3/4'ü o hafta
işlenen konunun kalan testlerinin boş günlere YAYILMASI. Yayma boşluğa göre
yapılır → gün başına test kapasitesi gerekir (geçmişten öğrenilir, koç düzeltir).

- weekly_skeleton_slots + is_anchor (BOOLEAN NOT NULL, varsayılan false):
  "okulda/dershanede işlenen ders" satırı
- weekly_skeletons + day_capacity (TEXT, nullable): hafta günü → test
  kapasitesi, koçun ELLE düzelttiği değerler (JSON {"0": 20, …}); boş gün
  anahtarı = geçmişten öğrenilen değer kullanılır
Additive, mevcut satırlar etkilenmez, downgrade'li.
"""
from alembic import op
import sqlalchemy as sa

revision = "e6f9i2j3i77e"
down_revision = "d5e8h1i2h66d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("weekly_skeleton_slots") as b:
        b.add_column(sa.Column("is_anchor", sa.Boolean(), nullable=False,
                               server_default=sa.false()))
    with op.batch_alter_table("weekly_skeletons") as b:
        b.add_column(sa.Column("day_capacity", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("weekly_skeletons") as b:
        b.drop_column("day_capacity")
    with op.batch_alter_table("weekly_skeleton_slots") as b:
        b.drop_column("is_anchor")
