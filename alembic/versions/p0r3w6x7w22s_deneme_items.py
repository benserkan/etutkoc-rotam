"""Deneme kalemleri — branş/genel deneme tanıma (D1, 2026-10-20).

`task_book_items`'a dört alan (hepsi nullable, additive):
  · exam_kind      'brans' | 'genel'  — NULL = eski davranış (test / kaynaksız konu /
                    eski kitapsız tam deneme [planned = soru])
  · exam_section   sınav türü (lgs / tyt / ayt_say …) — net cezası + seri anahtarı
  · subject_id     kitapsız branş denemesinin dersi (kitaplıda ders kitaptan gelir)
  · question_count deneme başına soru sayısı (öğrencinin girişte esnek değiştirebildiği
                    başlangıç değeri)

Yeni kural: exam_kind dolu kalemde 1 kalem = 1 deneme (planned_count = 1). Mevcut
satırlar DEĞİŞMEZ. Downgrade'li.

Revision ID: p0r3w6x7w22s
Revises: o9q2v5w6v11r
Create Date: 2026-10-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p0r3w6x7w22s"
down_revision: Union[str, None] = "o9q2v5w6v11r"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("task_book_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("exam_kind", sa.String(8), nullable=True))
        batch_op.add_column(sa.Column("exam_section", sa.String(16), nullable=True))
        batch_op.add_column(sa.Column("subject_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("question_count", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_task_book_items_subject_id", "subjects", ["subject_id"], ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_task_book_items_exam_kind", ["exam_kind"])


def downgrade() -> None:
    with op.batch_alter_table("task_book_items", schema=None) as batch_op:
        batch_op.drop_index("ix_task_book_items_exam_kind")
        batch_op.drop_constraint("fk_task_book_items_subject_id", type_="foreignkey")
        batch_op.drop_column("question_count")
        batch_op.drop_column("subject_id")
        batch_op.drop_column("exam_section")
        batch_op.drop_column("exam_kind")
