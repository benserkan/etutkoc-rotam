"""Deneme mükerrer koruması — exam_results.import_pdf_sha256

Revision ID: y0z3c6d7c11y
Revises: x9y2b5c6b00x
Create Date: 2026-09-19

Saha (öğrenci #163, 2026-09-19): aynı karne PDF'i iki kez aktarıldı; mevcut
koruma yalnız "aynı ad + tarih" bakıyor ve "yine de kaydet" ile geçiliyordu
→ aynı deneme iki kayıt oldu, konu×deneme analizi ikisini de saydı.

Katman 1 = belge parmak izi: yüklenen PDF'in SHA-256 özeti kayda yazılır;
aynı dosya ikinci kez gelince daha Gemini'ye gitmeden (kredi harcanmadan)
durdurulur. Additive, nullable; eski kayıtlar
`scripts/backfill_exam_pdf_sha.py` ile (PDF kanıtı zaten saklı) doldurulur.
"""
from alembic import op
import sqlalchemy as sa

revision = "y0z3c6d7c11y"
down_revision = "x9y2b5c6b00x"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("exam_results") as batch:
        batch.add_column(
            sa.Column("import_pdf_sha256", sa.String(length=64), nullable=True)
        )
    op.create_index(
        "ix_exam_results_student_pdf_sha",
        "exam_results",
        ["student_id", "import_pdf_sha256"],
    )


def downgrade() -> None:
    op.drop_index("ix_exam_results_student_pdf_sha", table_name="exam_results")
    with op.batch_alter_table("exam_results") as batch:
        batch.drop_column("import_pdf_sha256")
