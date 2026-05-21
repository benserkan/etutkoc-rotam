"""week_notes — öğretmenin haftalık programa eklediği madde madde notlar

Revision ID: d4f7i0h1g99b
Revises: c3e6h9g0f88a
Create Date: 2026-05-17 15:00:00.000000

Tek tablo: (student_id, week_start) için birden çok madde. body serbest metin.
order alanı görsel sıralamayı tutar. is_done ileride check özelliği için ayrılır
(şu an UI'da display-only).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4f7i0h1g99b"
down_revision: Union[str, None] = "c3e6h9g0f88a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "week_notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "is_done", sa.Boolean(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["users.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_week_notes_student_id", "week_notes", ["student_id"], unique=False,
    )
    op.create_index(
        "ix_week_notes_week_start", "week_notes", ["week_start"], unique=False,
    )
    op.create_index(
        "ix_week_notes_student_week", "week_notes",
        ["student_id", "week_start"], unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_week_notes_student_week", table_name="week_notes")
    op.drop_index("ix_week_notes_week_start", table_name="week_notes")
    op.drop_index("ix_week_notes_student_id", table_name="week_notes")
    op.drop_table("week_notes")
