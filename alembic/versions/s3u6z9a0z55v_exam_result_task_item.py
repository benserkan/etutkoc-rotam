"""Görev denemesi → Denemeler köprüsü (D3, 2026-10-20).

`exam_results.task_book_item_id`: görevde girilen deneme sonucundan (1 kalem = 1 deneme)
otomatik açılan kaydın kalem bağı (import_source="task"). Kalem silinince kayıt da gider
(CASCADE). Additive, downgrade'li.

Revision ID: s3u6z9a0z55v
Revises: r2t5y8z9y44u
Create Date: 2026-10-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "s3u6z9a0z55v"
down_revision: Union[str, None] = "r2t5y8z9y44u"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("exam_results", schema=None) as batch_op:
        batch_op.add_column(sa.Column("task_book_item_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_exam_results_task_book_item_id", "task_book_items",
            ["task_book_item_id"], ["id"], ondelete="CASCADE")
        batch_op.create_index("ix_exam_results_task_book_item_id", ["task_book_item_id"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("exam_results", schema=None) as batch_op:
        batch_op.drop_index("ix_exam_results_task_book_item_id")
        batch_op.drop_constraint("fk_exam_results_task_book_item_id", type_="foreignkey")
        batch_op.drop_column("task_book_item_id")
