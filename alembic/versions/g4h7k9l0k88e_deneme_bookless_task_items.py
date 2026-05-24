"""task_book_items: kitapsız 'deneme' kalemine izin (book_id/section_id nullable + label)

Revision ID: g4h7k9l0k88e
Revises: f3g6j8k9j77d
Create Date: 2026-05-24 12:00:00.000000

Additive / kısıt-gevşetme — mevcut satırların hepsinde book_id+section_id DOLU,
ETKİLENMEZ. Tam deneme (LGS/TYT) tek derse ait olmadığından kitap/bölüm seçmeden
girilebilsin diye: task_book_items.book_id ve book_section_id NULL'a izin verir +
deneme adını taşıyan `label` kolonu eklenir. Kitapsız kalem rezerv/kapasite
sistemini ATLAR; öğrenci görevi tamamlayınca completed_count = planned_count.

Downgrade'li (kitapsız satırları silip NOT NULL'ı geri ekler).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g4h7k9l0k88e"
down_revision: Union[str, None] = "f3g6j8k9j77d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("task_book_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("label", sa.String(length=255), nullable=True))
        batch_op.alter_column("book_id", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column("book_section_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # Kitapsız (deneme) kalemleri sil ki NOT NULL geri eklenebilsin.
    op.execute(
        "DELETE FROM task_book_items WHERE book_id IS NULL OR book_section_id IS NULL"
    )
    with op.batch_alter_table("task_book_items", schema=None) as batch_op:
        batch_op.alter_column("book_section_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("book_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column("label")
