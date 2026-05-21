"""pomodoro_sessions + student_badges (Stage 14 — focus + gamification)

Revision ID: j8e4h7f8g77b
Revises: i7d3g6e7f66a
Create Date: 2026-05-11 12:00:00.000000

Stage 14 — Pomodoro + Light Gamification:
- pomodoro_sessions: tek pomodoro seansı (work/short_break/long_break)
- student_badges: kazanılan rozet kaydı (idempotent: student+kind unique)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j8e4h7f8g77b"
down_revision: Union[str, None] = "i7d3g6e7f66a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pomodoro_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column(
            "kind", sa.String(length=20), nullable=False, server_default="work"
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "planned_minutes", sa.Integer(), nullable=False, server_default=sa.text("25")
        ),
        sa.Column(
            "actual_minutes", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "interrupted", sa.Boolean(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pomodoro_sessions_student_id", "pomodoro_sessions", ["student_id"]
    )
    op.create_index(
        "ix_pomodoro_sessions_started_at", "pomodoro_sessions", ["started_at"]
    )

    op.create_table(
        "student_badges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("badge_kind", sa.String(length=48), nullable=False),
        sa.Column(
            "earned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "badge_kind", name="uq_student_badge"),
    )
    op.create_index("ix_student_badges_student_id", "student_badges", ["student_id"])
    op.create_index("ix_student_badges_badge_kind", "student_badges", ["badge_kind"])
    op.create_index(
        "ix_student_badge_earned", "student_badges", ["student_id", "earned_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_student_badge_earned", table_name="student_badges")
    op.drop_index("ix_student_badges_badge_kind", table_name="student_badges")
    op.drop_index("ix_student_badges_student_id", table_name="student_badges")
    op.drop_table("student_badges")

    op.drop_index("ix_pomodoro_sessions_started_at", table_name="pomodoro_sessions")
    op.drop_index("ix_pomodoro_sessions_student_id", table_name="pomodoro_sessions")
    op.drop_table("pomodoro_sessions")
