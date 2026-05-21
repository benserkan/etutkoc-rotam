"""exam_results: deneme sınavı sonuçları (KP4a — Akademik Çıktı)

Revision ID: r9s1v4w5v33p
Revises: q8r0u3v4u22o
Create Date: 2026-05-20 16:00:00.000000

Additive — yalnız yeni tablo (exam_results). Mevcut veriyi ETKİLEMEZ.
Öğretmen, öğrencisinin deneme sonucunu (doğru/yanlış/boş + ders kırılımı)
girer; net sınav türüne göre hesaplanır (LGS: D-Y/3, YKS: D-Y/4). Downgrade'li.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "r9s1v4w5v33p"
down_revision: Union[str, None] = "q8r0u3v4u22o"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exam_results",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=False),
        sa.Column(
            "section",
            sa.Enum("LGS", "TYT", "AYT_SAY", "AYT_EA", "AYT_SOZ", "AYT_DIL", name="examsection"),
            nullable=False,
        ),
        sa.Column("total_correct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_wrong", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_blank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("net", sa.Float(), nullable=False, server_default="0"),
        sa.Column("subject_nets", sa.Text(), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["users.id"], ondelete="CASCADE",
            name="fk_exam_results_student_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], ondelete="SET NULL",
            name="fk_exam_results_created_by_id_users",
        ),
    )
    op.create_index(
        "ix_exam_results_student_id", "exam_results", ["student_id"], unique=False,
    )
    op.create_index(
        "ix_exam_result_student_date", "exam_results", ["student_id", "exam_date"], unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_exam_result_student_date", table_name="exam_results")
    op.drop_index("ix_exam_results_student_id", table_name="exam_results")
    op.drop_table("exam_results")
