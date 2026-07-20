"""Bağımsız çalışma kayıtları (self_study_entries) + section_progress.manual_count

Tatil/koçsuz dönemde öğrencinin kendi başına çözdüğü testlerin İZLİ kaydı:
- self_study_entries: kim girdi (öğrenci beyanı / koç girişi), ne zaman, hangi
  bölüm, kaç test, hangi dönem, onay durumu. Eski anonim "zaten çözülmüştü"
  sayacının yerine geçer (provenance — manipülasyon görünür ve geri alınabilir).
- section_progress.manual_count: completed_count'un görev DIŞI (elle/bağımsız)
  gelen kısmı. completed = görevle çözülen + manual. Azaltma yalnız manual
  kısımdan yapılabilir (görevle çözülen görev üzerinden düzeltilir).

Additive — mevcut veriyi ETKİLEMEZ (manual_count=0 başlar; geçmiş elle girişler
scripts/backfill_manual_progress.py ile türetilir). Downgrade'li.

Revision ID: x8y1b4c5b77x
Revises: w7x0a3b4a66w
Create Date: 2026-07-20
"""
from alembic import op
import sqlalchemy as sa

revision = "x8y1b4c5b77x"
down_revision = "w7x0a3b4a66w"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "section_progress",
        sa.Column("manual_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "self_study_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "student_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
        ),
        sa.Column(
            "student_book_id", sa.Integer(),
            sa.ForeignKey("student_books.id", ondelete="CASCADE"), nullable=False, index=True,
        ),
        sa.Column(
            "book_section_id", sa.Integer(),
            sa.ForeignKey("book_sections.id", ondelete="CASCADE"), nullable=False, index=True,
        ),
        sa.Column("test_count", sa.Integer(), nullable=False),
        sa.Column("applied_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=16), nullable=False),  # student|coach
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column(
            "created_by_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "reviewed_by_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_self_study_student_status", "self_study_entries", ["student_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_self_study_student_status", table_name="self_study_entries")
    op.drop_table("self_study_entries")
    op.drop_column("section_progress", "manual_count")
