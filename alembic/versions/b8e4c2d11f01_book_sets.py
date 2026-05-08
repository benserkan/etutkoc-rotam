"""book_sets and book_set_items tables

Revision ID: b8e4c2d11f01
Revises: 1af3c861b592
Create Date: 2026-05-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8e4c2d11f01"
down_revision: Union[str, None] = "1af3c861b592"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "book_sets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("book_sets", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_book_sets_teacher_id"), ["teacher_id"], unique=False
        )

    op.create_table(
        "book_set_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("set_id", sa.Integer(), nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["set_id"], ["book_sets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("set_id", "book_id", name="uq_book_set_item"),
    )
    with op.batch_alter_table("book_set_items", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_book_set_items_set_id"), ["set_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_book_set_items_book_id"), ["book_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("book_set_items", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_book_set_items_book_id"))
        batch_op.drop_index(batch_op.f("ix_book_set_items_set_id"))
    op.drop_table("book_set_items")

    with op.batch_alter_table("book_sets", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_book_sets_teacher_id"))
    op.drop_table("book_sets")
