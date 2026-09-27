"""Kitabın kaynağı — katalog / koç şablonu / elle (2026-09-27)

Koç: "kitap ata ekranında hangisi şablondan geliyor, hangisi koç tarafından
manuel oluşturuldu belli değil". Kitap tablosu kaynağını hiç saklamıyordu.

- books + source_kind (VARCHAR(16), nullable): 'catalog' (Ortak Kitap
  Kataloğu kaydından) · 'template' (koçun kendi şablonundan) · 'manual'
  (elle girildi). NULL = bilinmiyor (eski kayıt; backfill betiği doldurur).
- books + source_template_id (INTEGER, nullable, FK book_templates SET NULL).
Additive, mevcut satırlar etkilenmez, downgrade'li.
"""
from alembic import op
import sqlalchemy as sa

revision = "g8h1k4l5k99g"
down_revision = "f7g0j3k4j88f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("books") as b:
        b.add_column(sa.Column("source_kind", sa.String(length=16), nullable=True))
        b.add_column(sa.Column("source_template_id", sa.Integer(), nullable=True))
        b.create_foreign_key(
            "fk_books_source_template_id", "book_templates",
            ["source_template_id"], ["id"], ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("books") as b:
        b.drop_constraint("fk_books_source_template_id", type_="foreignkey")
        b.drop_column("source_template_id")
        b.drop_column("source_kind")
