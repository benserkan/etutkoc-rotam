"""book_sets target_grade columns

Set'lere hedef sınıf seviyesi alanları (Book modelindekiyle aynı semantik):
  - target_grade_min, target_grade_max (NULL = belirtilmemiş)
  - target_graduate (default False)

Mevcut satırlarda 3 alan da varsayılan: NULL/NULL/False → "Tüm seviyeler"
yorumu (geriye uyumlu).

Revision ID: n5o7r0s1r99l
Revises: m4n6q9r0q88k
Create Date: 2026-05-19 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n5o7r0s1r99l"
down_revision: Union[str, None] = "m4n6q9r0q88k"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("book_sets", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("target_grade_min", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("target_grade_max", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "target_graduate",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("book_sets", schema=None) as batch_op:
        batch_op.drop_column("target_graduate")
        batch_op.drop_column("target_grade_max")
        batch_op.drop_column("target_grade_min")
