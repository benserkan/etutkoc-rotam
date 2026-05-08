"""lise + YKS + mezun genişlemesi — Faz 1 veri modeli

Revision ID: h0c6f8d9e909
Revises: g9b5e7c8d808
Create Date: 2026-05-08 00:00:00.000000

Sistem 8. sınıf LGS odaklı kuruluydu; bu migration veri modelini 9-12. sınıf
lise + üniversite mezunu YKS hazırlığı öğrencileri kapsayacak şekilde
genişletir. Mevcut tüm data 8. sınıf/LGS varsayılır (geriye %100 uyum).

Eklenen alanlar:
- users.is_graduate (Boolean) — mezun işareti
- users.track (Enum) — YKS alan tercihi (sayısal/ea/sözel/dil), 11+ zorunlu
- users.graduate_mode (Enum) — mezun çalışma şekli (full_time/dershane)
- subjects.min_grade_level / max_grade_level (Int|null) — ders kapsam aralığı
- subjects.available_for_graduate (Bool) — mezun YKS programında geçer mi
- subjects.exam_section (Enum) — TYT / AYT_SAY/EA/SOZ/DIL / LGS
- books.target_grade_min / target_grade_max (Int|null) — kitap hedef aralığı
- books.target_graduate (Bool) — mezun için kullanılır mı
- academic_years.exam_target (Enum) — LGS / YKS / NONE

Schema değişikliği:
- topics.grade_level NOT NULL → nullable (mevcut değerler korunur)

Backfill (mevcut data 8. sınıf/LGS olarak kabul edilir):
- subjects: min_grade_level=5, max_grade_level=8, exam_section='lgs'
- books: target_grade_min=8, target_grade_max=8
- academic_years: exam_target='lgs'
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h0c6f8d9e909"
down_revision: Union[str, None] = "g9b5e7c8d808"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# SQLAlchemy Enum default'u Python enum **member adlarını** saklar (örn 'LGS'),
# value'ları DEĞİL ('lgs'). Mevcut projede tüm enum'lar (UserRole, BookType,
# NotificationKind …) bu kuralla çalışıyor — tutarlı kalmak için aynısını
# yapıyoruz. Bu listeler DB CHECK constraint için kullanılır (SQLite'da
# `IN (...)`), uppercase olmalı.
TRACK_VALUES = ("SAYISAL", "EA", "SOZEL", "DIL")
GRADUATE_MODE_VALUES = ("FULL_TIME", "DERSHANE")
EXAM_SECTION_VALUES = ("LGS", "TYT", "AYT_SAY", "AYT_EA", "AYT_SOZ", "AYT_DIL")
EXAM_TARGET_VALUES = ("LGS", "YKS", "NONE")


def upgrade() -> None:
    # ---------------- users ----------------
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column(
                "is_graduate",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch.add_column(
            sa.Column(
                "track",
                sa.Enum(*TRACK_VALUES, name="track"),
                nullable=True,
            )
        )
        batch.add_column(
            sa.Column(
                "graduate_mode",
                sa.Enum(*GRADUATE_MODE_VALUES, name="graduatemode"),
                nullable=True,
            )
        )

    # ---------------- subjects ----------------
    with op.batch_alter_table("subjects") as batch:
        batch.add_column(sa.Column("min_grade_level", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("max_grade_level", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column(
                "available_for_graduate",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch.add_column(
            sa.Column(
                "exam_section",
                sa.Enum(*EXAM_SECTION_VALUES, name="examsection"),
                nullable=True,
            )
        )

    # Backfill subjects: mevcut tüm dersleri LGS 5-8 olarak işaretle.
    # Builtin LGS dersleri için exam_section='lgs', öğretmen-özel olanlar
    # belirsiz olduğu için yine LGS 5-8 varsayılır (öğretmen sonra düzeltir).
    op.execute(
        "UPDATE subjects SET min_grade_level = 5, max_grade_level = 8, "
        "exam_section = 'LGS' WHERE min_grade_level IS NULL"
    )

    # ---------------- topics ----------------
    # grade_level NOT NULL → nullable. Mevcut değerler (default=8) korunur.
    with op.batch_alter_table("topics") as batch:
        batch.alter_column(
            "grade_level",
            existing_type=sa.Integer(),
            nullable=True,
            existing_server_default=sa.text("8"),
            server_default=None,
        )

    # ---------------- books ----------------
    with op.batch_alter_table("books") as batch:
        batch.add_column(sa.Column("target_grade_min", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("target_grade_max", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column(
                "target_graduate",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )

    # Mevcut kitaplar 8. sınıf LGS hazırlık → 8/8 hedef.
    op.execute(
        "UPDATE books SET target_grade_min = 8, target_grade_max = 8 "
        "WHERE target_grade_min IS NULL"
    )

    # ---------------- academic_years ----------------
    with op.batch_alter_table("academic_years") as batch:
        batch.add_column(
            sa.Column(
                "exam_target",
                sa.Enum(*EXAM_TARGET_VALUES, name="examtarget"),
                nullable=False,
                server_default="LGS",
            )
        )


def downgrade() -> None:
    # academic_years
    with op.batch_alter_table("academic_years") as batch:
        batch.drop_column("exam_target")

    # books
    with op.batch_alter_table("books") as batch:
        batch.drop_column("target_graduate")
        batch.drop_column("target_grade_max")
        batch.drop_column("target_grade_min")

    # topics — geri NOT NULL'a çevir; NULL kalan satırları 8 olarak doldur
    op.execute("UPDATE topics SET grade_level = 8 WHERE grade_level IS NULL")
    with op.batch_alter_table("topics") as batch:
        batch.alter_column(
            "grade_level",
            existing_type=sa.Integer(),
            nullable=False,
            server_default=sa.text("8"),
        )

    # subjects
    with op.batch_alter_table("subjects") as batch:
        batch.drop_column("exam_section")
        batch.drop_column("available_for_graduate")
        batch.drop_column("max_grade_level")
        batch.drop_column("min_grade_level")

    # users
    with op.batch_alter_table("users") as batch:
        batch.drop_column("graduate_mode")
        batch.drop_column("track")
        batch.drop_column("is_graduate")

    # Postgres-bound enum tiplerini temizle (SQLite'da no-op).
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for enum_name in ("track", "graduatemode", "examsection", "examtarget"):
            op.execute(f"DROP TYPE IF EXISTS {enum_name}")
