"""survey_system — öğrenci tanıma anket/envanter sistemi (Faz 1)

Revision ID: h1i4l7m8l55c
Revises: g0h3k6l7k44b
Create Date: 2026-06-11

Koç → öğrenci anket akışı: katalog şablonları (survey_templates +
survey_questions, idempotent seed ile dolar) + atama/cevap/skor
(survey_assignments). Additive, downgrade'li — mevcut veriyi ETKİLEMEZ.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h1i4l7m8l55c"
down_revision: Union[str, None] = "g0h3k6l7k44b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "survey_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column(
            "scoring_type", sa.String(20), nullable=False,
            server_default="dimensions",
        ),
        sa.Column("dimensions_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("report_note", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "source_attribution", sa.String(300), nullable=False, server_default="",
        ),
        sa.Column(
            "estimated_minutes", sa.Integer(), nullable=False, server_default="10",
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_by_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
    )
    op.create_index(
        "ix_survey_templates_category_sort",
        "survey_templates",
        ["category", "sort_order"],
    )

    op.create_table(
        "survey_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "template_id", sa.Integer(),
            sa.ForeignKey("survey_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("qtype", sa.String(20), nullable=False, server_default="likert5"),
        sa.Column("dimension_key", sa.String(40), nullable=True),
        sa.Column("options_json", sa.Text(), nullable=True),
        sa.Column("reverse", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_survey_questions_template_order",
        "survey_questions",
        ["template_id", "order_no"],
    )

    op.create_table(
        "survey_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "template_id", sa.Integer(),
            sa.ForeignKey("survey_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "teacher_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "student_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("answers_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("scores_json", sa.Text(), nullable=True),
        sa.Column(
            "assigned_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_survey_assignments_student_status",
        "survey_assignments",
        ["student_id", "status"],
    )
    op.create_index(
        "ix_survey_assignments_teacher",
        "survey_assignments",
        ["teacher_id", "assigned_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_survey_assignments_teacher", table_name="survey_assignments")
    op.drop_index(
        "ix_survey_assignments_student_status", table_name="survey_assignments"
    )
    op.drop_table("survey_assignments")
    op.drop_index("ix_survey_questions_template_order", table_name="survey_questions")
    op.drop_table("survey_questions")
    op.drop_index("ix_survey_templates_category_sort", table_name="survey_templates")
    op.drop_table("survey_templates")
