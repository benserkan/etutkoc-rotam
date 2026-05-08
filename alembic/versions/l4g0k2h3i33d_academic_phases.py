"""academic_phases tablosu — yıl içi dönem-tipi (yaz kampı, tatil, vb.)

Revision ID: l4g0k2h3i33d
Revises: k3f9j1g2h22c
Create Date: 2026-05-08 03:00:00.000000

Faz 6 — Akademik yıl içinde isteğe bağlı zaman dilimleri:
- REGULAR (olağan), WINTER_BREAK (yarıyıl tatil), SUMMER_CAMP (yaz kampı),
  EXAM_PREP (sınav hazırlık).
- Mevcut AcademicYear'lar için phase eklenmez; öğretmen sonradan tanımlar.
- Plan motoru entegrasyonu sonraki sprint'te (kapasite/günlük ders saati).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l4g0k2h3i33d"
down_revision: Union[str, None] = "k3f9j1g2h22c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# SQLAlchemy Enum default'u member adlarını saklar (UPPER-case).
PHASE_KIND_VALUES = ("REGULAR", "WINTER_BREAK", "SUMMER_CAMP", "EXAM_PREP")


def upgrade() -> None:
    op.create_table(
        "academic_phases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("academic_year_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(*PHASE_KIND_VALUES, name="academicphasekind"),
            nullable=False,
            server_default="REGULAR",
        ),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["academic_year_id"],
            ["academic_years.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_academic_phase_year", "academic_phases", ["academic_year_id"]
    )
    op.create_index(
        "ix_academic_phase_dates", "academic_phases", ["start_date", "end_date"]
    )


def downgrade() -> None:
    op.drop_index("ix_academic_phase_dates", table_name="academic_phases")
    op.drop_index("ix_academic_phase_year", table_name="academic_phases")
    op.drop_table("academic_phases")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS academicphasekind")
