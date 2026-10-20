"""Havuz deneme kalemleri (D1b, 2026-10-20).

`pool_items`'a deneme alanları (hepsi nullable, additive): exam_kind ('brans'|'genel'),
exam_section (lgs/tyt/ayt_say…), question_count (deneme başına soru). Havuz kalemi
deneme ise kaba alınınca her deneme ayrı görev kalemi olur (1 kalem = 1 deneme —
task_book_items ile aynı kural, app.services.deneme_service). Downgrade'li.

Revision ID: q1s4x7y8x33t
Revises: p0r3w6x7w22s
Create Date: 2026-10-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "q1s4x7y8x33t"
down_revision: Union[str, None] = "p0r3w6x7w22s"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("pool_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("exam_kind", sa.String(8), nullable=True))
        batch_op.add_column(sa.Column("exam_section", sa.String(16), nullable=True))
        batch_op.add_column(sa.Column("question_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("pool_items", schema=None) as batch_op:
        batch_op.drop_column("question_count")
        batch_op.drop_column("exam_section")
        batch_op.drop_column("exam_kind")
