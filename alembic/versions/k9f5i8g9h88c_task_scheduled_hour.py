"""task scheduled_hour column (Stage 15 — hour-based daily planning)

Revision ID: k9f5i8g9h88c
Revises: j8e4h7f8g77b
Create Date: 2026-05-12 14:00:00.000000

Manuel görev ekleme akışına opsiyonel saat alanı (0-23). NULL = saatsiz
(eski davranış). Set ise day_card'da saat etiketi gösterilir ve gün içi
sıralama (hour NULLS LAST, order, id) ile yapılır.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k9f5i8g9h88c"
down_revision: Union[str, None] = "j8e4h7f8g77b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(
            sa.Column("scheduled_hour", sa.Integer(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("scheduled_hour")
