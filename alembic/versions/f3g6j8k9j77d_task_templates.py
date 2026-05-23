"""task_templates + task_template_items: görev şablonu (sık kullanılan görev kalıbı)

Revision ID: f3g6j8k9j77d
Revises: e2f5i7j8i66c
Create Date: 2026-05-23 20:00:00.000000

Additive — 2 yeni tablo. Mevcut veriyi ETKİLEMEZ. Downgrade'li. BookTemplate
(kitap bölüm şablonu) ile İLGİSİZ; bu görev kalıplarını (kitap+bölüm+test sayısı)
saklar → haftalık planda tek tıkla görev oluşturma için.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3g6j8k9j77d"
down_revision: Union[str, None] = "e2f5i7j8i66c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_templates",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("type", sa.Enum("test", "video", "ozet", "tekrar", "other", name="tasktype", create_type=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], ondelete="CASCADE",
                                name="fk_task_templates_teacher_id_users"),
    )
    op.create_index("ix_task_templates_teacher_id", "task_templates", ["teacher_id"], unique=False)

    op.create_table(
        "task_template_items",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("book_section_id", sa.Integer(), nullable=False),
        sa.Column("planned_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["task_templates.id"], ondelete="CASCADE",
                                name="fk_task_template_items_template_id"),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE",
                                name="fk_task_template_items_book_id"),
        sa.ForeignKeyConstraint(["book_section_id"], ["book_sections.id"], ondelete="CASCADE",
                                name="fk_task_template_items_section_id"),
    )
    op.create_index("ix_task_template_items_template_id", "task_template_items", ["template_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_task_template_items_template_id", table_name="task_template_items")
    op.drop_table("task_template_items")
    op.drop_index("ix_task_templates_teacher_id", table_name="task_templates")
    op.drop_table("task_templates")
