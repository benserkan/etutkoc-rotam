"""Deneme PDF içe aktarma — exam_result_questions + exam_topic_aliases + ExamSection.OKUL

Revision ID: v6w9z2a3z55v
Revises: u5v8y1z2y44u
Create Date: 2026-07-16 00:00:00.000000

Additive — mevcut veriyi ETKİLEMEZ, downgrade'li.

- exam_result_questions: içe aktarılan denemenin soru-soru kaydı (ders/konu ham +
  normalize, DC/ÖC/sonuç, şüpheli/elle-düzeltildi izleri). Konu-bazlı hata
  birikimi analizinin (Faz 2) ham verisi.
- exam_topic_aliases: evren-anahtarlı ÖĞRENEN eşleme sözlüğü — yayınevi konu
  etiketi → resmi Topic. Bir kez kurulan eşleme sonsuza dek aynı çözülür
  (tutarlı birikim + AI maliyeti zamanla düşer).
- exam_results: içe aktarma izleri (kaynak + PDF kanıt + analiz meta).
- ExamSection enum'una 'OKUL' üyesi (okul/sınıf denemeleri). Postgres native
  enum → ALTER TYPE ADD VALUE (feedback-postgres-enum-new-member-migration);
  SQLite'ta Enum VARCHAR (SA 2.0 create_constraint=False) → işlem gerekmez.
  NOT: Postgres enum üyesi downgrade'de GERİ ALINMAZ (PG desteklemez; zararsız).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v6w9z2a3z55v"
down_revision: Union[str, None] = "u5v8y1z2y44u"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # PG12+ transaction içinde ADD VALUE destekler (aynı tx'te kullanmamak şartıyla)
        op.execute("ALTER TYPE examsection ADD VALUE IF NOT EXISTS 'OKUL'")

    # --- exam_results: içe aktarma izleri (hepsi nullable — manuel kayıtlar etkilenmez)
    op.add_column("exam_results", sa.Column("import_source", sa.String(length=16), nullable=True))
    op.add_column("exam_results", sa.Column("import_pdf_content_type", sa.String(length=100), nullable=True))
    op.add_column("exam_results", sa.Column("import_pdf_size", sa.Integer(), nullable=True))
    op.add_column("exam_results", sa.Column("import_pdf_data", sa.LargeBinary(), nullable=True))
    op.add_column("exam_results", sa.Column("analysis_meta", sa.Text(), nullable=True))

    # --- soru-soru kayıt
    op.create_table(
        "exam_result_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exam_result_id", sa.Integer(),
                  sa.ForeignKey("exam_results.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_no", sa.Integer(), nullable=True),
        sa.Column("subject_name_raw", sa.String(length=120), nullable=True),
        sa.Column("subject_id", sa.Integer(),
                  sa.ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("topic_label_raw", sa.String(length=200), nullable=True),
        sa.Column("topic_id", sa.Integer(),
                  sa.ForeignKey("topics.id", ondelete="SET NULL"), nullable=True),
        sa.Column("correct_answer", sa.String(length=8), nullable=True),
        sa.Column("student_answer", sa.String(length=8), nullable=True),
        sa.Column("result", sa.String(length=8), nullable=False, server_default="yanlis"),
        sa.Column("is_suspect", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("manually_edited", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_exam_result_questions_exam_result_id",
                    "exam_result_questions", ["exam_result_id"])
    op.create_index("ix_exam_result_questions_topic_id",
                    "exam_result_questions", ["topic_id"])
    op.create_index("ix_erq_exam_subject",
                    "exam_result_questions", ["exam_result_id", "subject_id"])

    # --- öğrenen eşleme sözlüğü (evren + ders + etiket anahtarı → konu)
    op.create_table(
        "exam_topic_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope", sa.String(length=16), nullable=False),  # tyt|ayt|lgs|okul
        sa.Column("subject_id", sa.Integer(),
                  sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("label_key", sa.String(length=200), nullable=False),
        sa.Column("label_raw", sa.String(length=200), nullable=True),
        sa.Column("topic_id", sa.Integer(),
                  sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(length=8), nullable=False, server_default="ai"),  # ai|coach
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("scope", "subject_id", "label_key",
                            name="uq_exam_topic_alias_scope_subject_label"),
    )
    op.create_index("ix_exam_topic_aliases_scope", "exam_topic_aliases", ["scope"])
    op.create_index("ix_exam_topic_aliases_topic_id", "exam_topic_aliases", ["topic_id"])


def downgrade() -> None:
    op.drop_index("ix_exam_topic_aliases_topic_id", table_name="exam_topic_aliases")
    op.drop_index("ix_exam_topic_aliases_scope", table_name="exam_topic_aliases")
    op.drop_table("exam_topic_aliases")
    op.drop_index("ix_erq_exam_subject", table_name="exam_result_questions")
    op.drop_index("ix_exam_result_questions_topic_id", table_name="exam_result_questions")
    op.drop_index("ix_exam_result_questions_exam_result_id", table_name="exam_result_questions")
    op.drop_table("exam_result_questions")
    op.drop_column("exam_results", "analysis_meta")
    op.drop_column("exam_results", "import_pdf_data")
    op.drop_column("exam_results", "import_pdf_size")
    op.drop_column("exam_results", "import_pdf_content_type")
    op.drop_column("exam_results", "import_source")
    # NOT: Postgres examsection enum'undaki 'OKUL' üyesi bilinçli bırakılır
    # (PG üye silmeyi desteklemez; kullanılmayan üye zararsızdır).
