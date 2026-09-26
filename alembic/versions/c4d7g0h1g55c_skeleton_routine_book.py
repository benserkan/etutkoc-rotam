"""Haftalık İskelet — kitaba bağlı rutin satırı (F2-1)

Revision ID: c4d7g0h1g55c
Revises: b3c6f9g0f44b
Create Date: 2026-09-26

weekly_skeleton_slots'a 3 nullable kolon (additive, mevcut satırlar etkilenmez,
downgrade'li):
- book_id: satırın kaynağı (rutin: rutinin kitabı; konu satırı: çiplerde önce
  bu kitabın ipliği). NULL = eski davranış
- label: kaynağın koça görünen adı — kitapsız (serbest metinli) görevden
  gelen satırda görev başlığı ("Bilgi Sarmal Problemler 2 Karma Test"), aynı
  derse birden çok satırda hangisinin rutin olduğu okunabilsin
- routine_mode: 'sirali' (kitapta sırayla, bölüm biterse sıradakine taşar) |
  'karma' (her gün FARKLI bölümlerden birer test, bölümler arasında döner —
  paragraf rutini: Sözcükte Anlam 1 · Cümlede Anlam 1 · …)
"""
from alembic import op
import sqlalchemy as sa

revision = "c4d7g0h1g55c"
down_revision = "b3c6f9g0f44b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("weekly_skeleton_slots") as b:
        b.add_column(sa.Column("book_id", sa.Integer(), nullable=True))
        b.add_column(sa.Column("routine_mode", sa.String(length=16), nullable=True))
        b.add_column(sa.Column("label", sa.String(length=160), nullable=True))
        b.create_foreign_key(
            "fk_weekly_skeleton_slots_book_id", "books", ["book_id"], ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("weekly_skeleton_slots") as b:
        b.drop_constraint("fk_weekly_skeleton_slots_book_id", type_="foreignkey")
        b.drop_column("label")
        b.drop_column("routine_mode")
        b.drop_column("book_id")
