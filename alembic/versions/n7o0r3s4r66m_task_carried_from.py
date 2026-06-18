"""tasks.carried_from_task_id — devredilen görevin kaynağı

Devret listesinden bir görev yeni güne taşınınca, oluşturulan YENİ görev hangi
kaynak görevden geldiğini tutar. Yeni görev silinirse kaynağın carried_at'i
temizlenir → görev tekrar "tamamlanmayanlar" listesine döner (geri-al). Kaynak
silinirse SET NULL. Additive, downgrade'li.

Revision ID: n7o0r3s4r66m
Revises: m6n9q2r3q55l
Create Date: 2026-06-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n7o0r3s4r66m"
down_revision: Union[str, None] = "m6n9q2r3q55l"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite ALTER-ADD-FK desteklemez → batch mode (work_block_id deseni).
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("carried_from_task_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_tasks_carried_from_task_id", ["carried_from_task_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_tasks_carried_from_task", "tasks",
            ["carried_from_task_id"], ["id"], ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_constraint("fk_tasks_carried_from_task", type_="foreignkey")
        batch_op.drop_index("ix_tasks_carried_from_task_id")
        batch_op.drop_column("carried_from_task_id")
