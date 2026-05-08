"""academic_years.start_year — kohort tahmininde kullanılan başlangıç yılı

Revision ID: j2e8h0f1g11b
Revises: i1d7g9e0f00a
Create Date: 2026-05-08 01:00:00.000000

Akademik yılın temsil ettiği Eylül-yılı (örn "2025-2026" → 2025) müfredat
modeli (Maarif/Klasik) tahmininde kullanılır. Öğretmen ad-hoc öğrenci
kaydederken: academic_year.start_year + student.grade_level'dan implicit
9'a giriş yılı türetilir (sınıf tekrarı yok varsayımıyla).

Backfill: mevcut name'lerden ilk 4 hane parse edilir ('2025-2026' → 2025).
Parse edilemezse NULL kalır (UI öğretmenden manuel girmesini isteyecek).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j2e8h0f1g11b"
down_revision: Union[str, None] = "i1d7g9e0f00a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("academic_years") as batch:
        batch.add_column(sa.Column("start_year", sa.Integer(), nullable=True))

    # Mevcut name'lerden parse — '2025-2026', '2026-2027' gibi formatlar
    # için ilk 4 hane tipik olarak Eylül-yılını temsil eder.
    # DB-agnostik: Python tarafında parse + güncelle (SQLite GLOB ile
    # Postgres regex farklılığını bypass eder).
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, name FROM academic_years WHERE start_year IS NULL")
    ).all()
    for row in rows:
        name = (row[1] or "").strip()
        if len(name) >= 4 and name[:4].isdigit():
            bind.execute(
                sa.text("UPDATE academic_years SET start_year = :y WHERE id = :i"),
                {"y": int(name[:4]), "i": row[0]},
            )


def downgrade() -> None:
    with op.batch_alter_table("academic_years") as batch:
        batch.drop_column("start_year")
