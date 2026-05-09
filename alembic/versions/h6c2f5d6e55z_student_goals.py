"""student_goals tablosu (Stage 11 — hedef ağacı)

Revision ID: h6c2f5d6e55z
Revises: g5b1e4c5d44y
Create Date: 2026-05-10 09:00:00.000000

Stage 11 — Goal Tree:
- student_goals: hiyerarşik öğrenci hedef düğümleri (parent_id self-FK)
- kind=exam_target/subject/topic/weekly/daily/custom
- status=active/achieved/abandoned
- target_value/current_value/unit (sayısal hedefler)
- target_date (sınav günü, hafta sonu)
- is_auto_generated (sistem türetti vs öğretmen ekledi)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h6c2f5d6e55z"
down_revision: Union[str, None] = "g5b1e4c5d44y"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "student_goals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column(
            "status", sa.String(length=20), nullable=False,
            server_default="active",
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_value", sa.Float(), nullable=True),
        sa.Column("current_value", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column(
            "is_auto_generated", sa.Boolean(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("achieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("abandoned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["users.id"],
            ondelete="CASCADE", name="fk_sg_student",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["student_goals.id"],
            ondelete="CASCADE", name="fk_sg_parent",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"],
            ondelete="SET NULL", name="fk_sg_created_by",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("student_goals") as batch:
        batch.create_index("ix_student_goals_student_id", ["student_id"])
        batch.create_index("ix_student_goals_student_status", ["student_id", "status"])
        batch.create_index("ix_student_goals_parent", ["parent_id"])
        batch.create_index("ix_student_goals_kind", ["kind"])
        batch.create_index("ix_student_goals_created_at", ["created_at"])


def downgrade() -> None:
    op.drop_table("student_goals")
