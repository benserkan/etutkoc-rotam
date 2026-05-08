"""book_templates + book_template_sections — yeniden kullanılabilir kitap yapı şablonları

Revision ID: n6i2m4j5k55f
Revises: m5h1l3i4j44e
Create Date: 2026-05-08 22:00:00.000000

Yeni kitap eklerken sıfırdan ünite girmek yerine bir şablona uygulanarak hızla
doldurulabilir. AI önerileri de aynı modele kaydedilir (is_ai_generated=True);
kullanıcı düzenleyip onayladığında is_verified=True olur.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n6i2m4j5k55f"
down_revision: Union[str, None] = "m5h1l3i4j44e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "book_templates",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column(
            "type",
            sa.Enum(
                "SORU_BANKASI", "FASIKUL", "KONU_ANLATIMLI",
                "BRANS_DENEMESI", "GENEL_DENEME",
                name="booktype",
            ),
            nullable=False,
        ),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("target_grade_min", sa.Integer(), nullable=True),
        sa.Column("target_grade_max", sa.Integer(), nullable=True),
        sa.Column("target_graduate", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("avg_questions_per_test", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_ai_generated", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_book_templates_teacher_id", "book_templates", ["teacher_id"]
    )
    op.create_index(
        "ix_book_templates_subject_id", "book_templates", ["subject_id"]
    )

    op.create_table(
        "book_template_sections",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("default_test_count", sa.Integer(), nullable=False, server_default=sa.text("10")),
        sa.Column("order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["template_id"], ["book_templates.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_book_template_sections_template_id",
        "book_template_sections",
        ["template_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_book_template_sections_template_id", table_name="book_template_sections")
    op.drop_table("book_template_sections")
    op.drop_index("ix_book_templates_subject_id", table_name="book_templates")
    op.drop_index("ix_book_templates_teacher_id", table_name="book_templates")
    op.drop_table("book_templates")
