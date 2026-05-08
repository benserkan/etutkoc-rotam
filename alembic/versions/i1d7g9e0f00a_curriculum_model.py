"""müfredat modeli — Maarif/Klasik kohort ayrımı (Faz 1.5)

Revision ID: i1d7g9e0f00a
Revises: h0c6f8d9e909
Create Date: 2026-05-08 00:30:00.000000

Türkiye'nin Maarif Modeli geçişine duyarlı müfredat versiyonlama:
- 2024-25'ten itibaren 9'a başlayan kohortlar Maarif görüyor
- Önceki kohortlar Klasik (2026-27'de son 12'ye geçiş, 2027-28'de mezun)
- Aynı sınıf seviyesinde (örn 11) iki müfredat paralel yaşar bir süreliğine

Eklenen alanlar:
- users.entry_year_grade9 (Int|null) — kohort tanımlayıcı
- subjects.curriculum_model (Enum|null) — ders hangi modele ait
- topics.curriculum_model (Enum|null) — konu hangi modele ait

Backfill:
- Mevcut subjects/topics tümü LGS müfredatına ait → curriculum_model='LGS'
- users.entry_year_grade9 NULL kalır (mevcut öğrenciler 5-8 LGS, kohort
  bilgisi anlamsız; 9-12 öğrencileri eklenirken UI tahmin yapacak)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i1d7g9e0f00a"
down_revision: Union[str, None] = "h0c6f8d9e909"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# SQLAlchemy Enum default'u member adlarını saklar (UPPER-case).
CURRICULUM_MODEL_VALUES = ("LGS", "KLASIK_LISE", "MAARIF_LISE")


def upgrade() -> None:
    # ---------------- users ----------------
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("entry_year_grade9", sa.Integer(), nullable=True)
        )

    # ---------------- subjects ----------------
    with op.batch_alter_table("subjects") as batch:
        batch.add_column(
            sa.Column(
                "curriculum_model",
                sa.Enum(*CURRICULUM_MODEL_VALUES, name="curriculummodel"),
                nullable=True,
            )
        )

    # Mevcut tüm subject'ler LGS müfredatına ait (sistem 8.sınıf odaklı kurulduydu).
    op.execute("UPDATE subjects SET curriculum_model = 'LGS' WHERE curriculum_model IS NULL")

    # ---------------- topics ----------------
    with op.batch_alter_table("topics") as batch:
        batch.add_column(
            sa.Column(
                "curriculum_model",
                sa.Enum(*CURRICULUM_MODEL_VALUES, name="curriculummodel"),
                nullable=True,
            )
        )

    op.execute("UPDATE topics SET curriculum_model = 'LGS' WHERE curriculum_model IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("topics") as batch:
        batch.drop_column("curriculum_model")

    with op.batch_alter_table("subjects") as batch:
        batch.drop_column("curriculum_model")

    with op.batch_alter_table("users") as batch:
        batch.drop_column("entry_year_grade9")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS curriculummodel")
