"""task_book_items book/section FK'ları RESTRICT → SET NULL (güvenlik ağı)

Revision ID: p6q9t2v3v66p
Revises: o5p8s1u2u55o
Create Date: 2026-08-14 00:00:00.000000

Saha bug'ı (2026-08-14): görev geçmişi kalmış kitap/bölüm silinince FK ihlali
→ 500 (11 hata grubu). Birincil çözüm uygulama katmanında (library silme
uçları kalemleri label doldurarak koparır — geçmiş korunur); bu migration
UYGULAMA DIŞI silme yolları (admin kullanıcı silme CASCADE → books →
book_sections) için son savunma hattı: FK artık satırı NULL'lar, 500 atmaz.

SQLite (dev): FK pragma kapalı + constraint yeniden kurmak tablo yeniden
yaratmayı gerektirir → atlanır (dev'de FK zaten uygulanmıyor).
"""
from typing import Sequence, Union

from alembic import op


revision: str = "p6q9t2v3v66p"
down_revision: Union[str, None] = "o5p8s1u2u55o"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgres():
        return
    op.drop_constraint("task_book_items_book_id_fkey", "task_book_items", type_="foreignkey")
    op.create_foreign_key(
        "task_book_items_book_id_fkey", "task_book_items", "books",
        ["book_id"], ["id"], ondelete="SET NULL",
    )
    op.drop_constraint("task_book_items_book_section_id_fkey", "task_book_items", type_="foreignkey")
    op.create_foreign_key(
        "task_book_items_book_section_id_fkey", "task_book_items", "book_sections",
        ["book_section_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    if not _is_postgres():
        return
    op.drop_constraint("task_book_items_book_id_fkey", "task_book_items", type_="foreignkey")
    op.create_foreign_key(
        "task_book_items_book_id_fkey", "task_book_items", "books",
        ["book_id"], ["id"], ondelete="RESTRICT",
    )
    op.drop_constraint("task_book_items_book_section_id_fkey", "task_book_items", type_="foreignkey")
    op.create_foreign_key(
        "task_book_items_book_section_id_fkey", "task_book_items", "book_sections",
        ["book_section_id"], ["id"], ondelete="RESTRICT",
    )
