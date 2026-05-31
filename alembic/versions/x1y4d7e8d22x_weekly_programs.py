"""WP1 — Weekly Programs: koç yeni program oluştur akışı.

Kullanıcı (2026-05-31): "Anchor" kavramı kafa karıştırıcı; her programın
açıkça başlangıç+bitiş tarihi olsun. Bayram gibi durumlar yeni program
yaratmakla doğal handle edilir.

Tablo: weekly_programs
  - student_id (FK CASCADE)
  - coach_id   (FK SET NULL — koç silinirse program durur)
  - start_date / end_date (her ikisi dahil; süre 1-14 gün — endpoint validation)
  - name (opsiyonel etiket: "Bayram Haftası" gibi)
  - notes (opsiyonel)
  - created_at / updated_at

Task tablosu DEĞİŞMEZ — görevler hâlâ Task.date ile durur. Program "tarih
aralığı kapısı" gibi davranır: aktif program = today ∈ [start_date, end_date];
gösterilecek görevler = Task.date BETWEEN start AND end.

Geri uyumluluk: program yoksa hafta sayfası mevcut anchor-blok mantığını
kullanır (kademeli geçiş, bozulma yok).

Additive + downgrade'li, mevcut veriyi etkilemez.
"""
from alembic import op
import sqlalchemy as sa


revision = "x1y4d7e8d22x"
down_revision = "w0x3c6d7c11w"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weekly_programs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "coach_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # En sık sorgular: öğrenci × tarih aralığı (aktif program detection)
    op.create_index(
        "ix_weekly_programs_student_dates",
        "weekly_programs",
        ["student_id", "start_date", "end_date"],
        unique=False,
    )
    op.create_index(
        "ix_weekly_programs_coach_id",
        "weekly_programs",
        ["coach_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_weekly_programs_coach_id", table_name="weekly_programs")
    op.drop_index("ix_weekly_programs_student_dates", table_name="weekly_programs")
    op.drop_table("weekly_programs")
