"""Yanlış Soru Arşivi — wrong_questions + wrong_question_images

Revision ID: u5v8y1z2y44u
Revises: t4u7x0y1x33t
Create Date: 2026-07-13 00:00:00.000000

Additive — mevcut veriyi ETKİLEMEZ, downgrade'li.

- wrong_questions: öğrencinin arşivlediği yanlış/boş soru; kaynak bağları
  (task/book_section/exam_result SET NULL), etiketler (subject/topic), hata
  türü, AI etiket çıktıları (Faz 3), kapanış yaşam döngüsü + FSRS alanları.
- wrong_question_images: soru/çözüm fotoğrafı (LargeBinary, model'de deferred).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "u5v8y1z2y44u"
down_revision: Union[str, None] = "t4u7x0y1x33t"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wrong_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("subject_id", sa.Integer(),
                  sa.ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("topic_id", sa.Integer(),
                  sa.ForeignKey("topics.id", ondelete="SET NULL"), nullable=True),
        sa.Column("book_id", sa.Integer(),
                  sa.ForeignKey("books.id", ondelete="SET NULL"), nullable=True),
        sa.Column("book_section_id", sa.Integer(),
                  sa.ForeignKey("book_sections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("task_id", sa.Integer(),
                  sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("exam_result_id", sa.Integer(),
                  sa.ForeignKey("exam_results.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_kind", sa.String(length=16), nullable=False,
                  server_default="diger"),
        sa.Column("error_type", sa.String(length=24), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("coach_note", sa.Text(), nullable=True),
        sa.Column("ai_question_text", sa.Text(), nullable=True),
        sa.Column("ai_hint", sa.Text(), nullable=True),
        sa.Column("ai_tagged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("difficulty_guess", sa.String(length=8), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False,
                  server_default="acik"),
        sa.Column("correct_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempts_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fsrs_state", sa.String(length=12), nullable=False,
                  server_default="new"),
        sa.Column("fsrs_stability", sa.Float(), nullable=False, server_default="0"),
        sa.Column("fsrs_difficulty", sa.Float(), nullable=False, server_default="0"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_wrong_questions_student_id", "wrong_questions", ["student_id"])
    op.create_index("ix_wrong_questions_topic_id", "wrong_questions", ["topic_id"])
    op.create_index("ix_wrong_questions_status", "wrong_questions", ["status"])
    op.create_index("ix_wrong_q_student_status", "wrong_questions", ["student_id", "status"])
    op.create_index("ix_wrong_q_student_due", "wrong_questions", ["student_id", "due_at"])
    op.create_index("ix_wrong_q_student_topic", "wrong_questions", ["student_id", "topic_id"])

    op.create_table(
        "wrong_question_images",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("wrong_question_id", sa.Integer(),
                  sa.ForeignKey("wrong_questions.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("kind", sa.String(length=12), nullable=False,
                  server_default="question"),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_wrong_question_images_wrong_question_id",
                    "wrong_question_images", ["wrong_question_id"])


def downgrade() -> None:
    op.drop_index("ix_wrong_question_images_wrong_question_id",
                  table_name="wrong_question_images")
    op.drop_table("wrong_question_images")
    op.drop_index("ix_wrong_q_student_topic", table_name="wrong_questions")
    op.drop_index("ix_wrong_q_student_due", table_name="wrong_questions")
    op.drop_index("ix_wrong_q_student_status", table_name="wrong_questions")
    op.drop_index("ix_wrong_questions_status", table_name="wrong_questions")
    op.drop_index("ix_wrong_questions_topic_id", table_name="wrong_questions")
    op.drop_index("ix_wrong_questions_student_id", table_name="wrong_questions")
    op.drop_table("wrong_questions")
