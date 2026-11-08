"""task_book_items.combined_into_id + combined_count — toplu deneme sonucu

Revision ID: z0b3g6h7g22c
Revises: y9a2f5g6f11b
Create Date: 2026-11-08

Öğrenci birden çok branş denemesinin toplamını tek satıra girebilir. Sonucu taşıyan
kalemde combined_count = deneme adedi; birlikte girilen diğer kalemler combined_into_id
ile ona bağlanır (çözüldü sayılır, "sonuç bekliyor" olmaz). Additive.
"""
import sqlalchemy as sa
from alembic import op

revision = "z0b3g6h7g22c"
down_revision = "y9a2f5g6f11b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("task_book_items") as b:
        b.add_column(sa.Column("combined_into_id", sa.Integer(), nullable=True))
        b.add_column(sa.Column("combined_count", sa.Integer(), nullable=True))
        b.create_foreign_key("fk_tbi_combined_into", "task_book_items",
                             ["combined_into_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    with op.batch_alter_table("task_book_items") as b:
        b.drop_constraint("fk_tbi_combined_into", type_="foreignkey")
        b.drop_column("combined_count")
        b.drop_column("combined_into_id")
