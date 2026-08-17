"""task_book_items.blank_count — öğrenci D/Y girişine boş sayısı eklendi

Revision ID: q7r0u3w4w77q
Revises: p6q9t2v3v66p
Create Date: 2026-08-17 00:00:00.000000

Öğrenci görev kaleminde doğru/yanlış yanında BOŞ sayısını da girer; koç
kaç sorunun gerçekten çözüldüğünü (D+Y) ve kaçının boş bırakıldığını görür.
Additive — mevcut satırlar NULL kalır (boş girilmemiş = bilinmiyor).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "q7r0u3w4w77q"
down_revision: Union[str, None] = "p6q9t2v3v66p"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "task_book_items",
        sa.Column("blank_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("task_book_items", "blank_count")
