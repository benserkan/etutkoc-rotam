"""Görev kalemine birim + sayfa aralığı (2026-10-22).

`task_book_items.unit` (test | soru | sayfa; NULL = test — eski kayıtlar birebir) +
`page_from` / `page_to`: kaynaksız konulu görev sayfa ya da soru birimiyle verilebilir
("Basınç (Hız Fen): s. 45–50"). Sayfa/soru kalemi müfredat konusuna bağlı kalır ama
TEST hacmine girmez. Havuz kalemine de aynı sayfa aralığı.
`tasks.topic_id`: konu seçiliyken verilen video/özet/tekrar/diğer görevi müfredat konusuna
bağlanır (tamamlanınca konu "çalışıldı"; test sayısına girmez). Additive, downgrade'li.

Revision ID: u5w8b1c2b77x
Revises: t4v7a0b1a66w
Create Date: 2026-10-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "u5w8b1c2b77x"
down_revision: Union[str, None] = "t4v7a0b1a66w"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("task_book_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("unit", sa.String(length=8), nullable=True))
        batch_op.add_column(sa.Column("page_from", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("page_to", sa.Integer(), nullable=True))
    with op.batch_alter_table("pool_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("page_from", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("page_to", sa.Integer(), nullable=True))
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("topic_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_tasks_topic_id", "topics", ["topic_id"], ["id"], ondelete="SET NULL")
        batch_op.create_index("ix_tasks_topic_id", ["topic_id"])


def downgrade() -> None:
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_index("ix_tasks_topic_id")
        batch_op.drop_constraint("fk_tasks_topic_id", type_="foreignkey")
        batch_op.drop_column("topic_id")
    with op.batch_alter_table("pool_items", schema=None) as batch_op:
        batch_op.drop_column("page_to")
        batch_op.drop_column("page_from")
    with op.batch_alter_table("task_book_items", schema=None) as batch_op:
        batch_op.drop_column("page_to")
        batch_op.drop_column("page_from")
        batch_op.drop_column("unit")
