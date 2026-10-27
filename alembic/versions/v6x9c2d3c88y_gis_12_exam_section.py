"""ExamSection'a GIS_12 — 12. sınıf / mezun Gelişim İzleme (AYT tabanlı)

Revision ID: v6x9c2d3c88y
Revises: u5w8b1c2b77x
Create Date: 2026-10-27

Koç (2026-10-27): 12. sınıf (bu yıl Klasik) öğrencisi TYT, AYT ve o güne kadar
işlenen AYT konularını kapsayan, soru sayısı değişken "Gelişim İzleme" sınavlarına
girer. Bu denemeler sistemde karşılığı olmadığı için "Okul Denemesi" olarak
kaydediliyordu. Postgres native enum → ALTER TYPE ADD VALUE
([[feedback-postgres-enum-new-member-migration]]); SQLite'ta VARCHAR, no-op.
Additive; downgrade no-op (Postgres enum üyesi düşürülemez).
"""
from alembic import op

revision = "v6x9c2d3c88y"
down_revision = "u5w8b1c2b77x"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("ALTER TYPE examsection ADD VALUE IF NOT EXISTS 'GIS_12'")


def downgrade() -> None:
    pass
