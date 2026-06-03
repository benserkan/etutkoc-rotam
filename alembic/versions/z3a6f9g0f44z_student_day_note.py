"""student_day_notes — öğrencinin gün-bazlı serbest düşünce notu (autosave)

Öğrenci /student/day'de o günün akışına dair serbest yorum/açıklama yazar; her
yazışta otomatik kaydedilir (buton yok), tekrar açınca kaldığı yerden devam eder.
Koç bu notu (salt-okuma) görür. Öğrenci+tarih başına TEK kayıt (unique).

Additive — yeni tablo; mevcut veriyi ETKİLEMEZ. Downgrade'li.

Revision ID: z3a6f9g0f44z
Revises: y2z5e8f9e33y
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "z3a6f9g0f44z"
down_revision = "y2z5e8f9e33y"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_day_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("student_id", "date", name="uq_student_day_note"),
    )
    op.create_index("ix_student_day_notes_student_id", "student_day_notes", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_student_day_notes_student_id", table_name="student_day_notes")
    op.drop_table("student_day_notes")
