"""student_grade_periods — öğrenci sınıf dönemi sınırları (P2, 2026-09-04)

Additive: yalnız yeni tablo. Mevcut veriye DOKUNMAZ; hiçbir görünüm bu
migration ile değişmez (dönem yalnız kaydedilir, filtreleme P3'te gelir).

Revision ID: s3t6w9x0w55s
Revises: r8s1v4x5x88r
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "s3t6w9x0w55s"
down_revision = "r8s1v4x5x88r"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_grade_periods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("grade_level", sa.Integer(), nullable=True),
        sa.Column(
            "is_graduate", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("curriculum_model", sa.String(length=32), nullable=True),
        sa.Column("track", sa.String(length=16), nullable=True),
        sa.Column("academic_year_id", sa.Integer(), nullable=True),
        sa.Column("started_on", sa.Date(), nullable=False),
        sa.Column("ended_on", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["academic_year_id"], ["academic_years.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_student_grade_periods_student_id",
        "student_grade_periods",
        ["student_id"],
    )
    op.create_index(
        "ix_sgp_student_started",
        "student_grade_periods",
        ["student_id", "started_on"],
    )


def downgrade() -> None:
    op.drop_index("ix_sgp_student_started", table_name="student_grade_periods")
    op.drop_index(
        "ix_student_grade_periods_student_id", table_name="student_grade_periods"
    )
    op.drop_table("student_grade_periods")
