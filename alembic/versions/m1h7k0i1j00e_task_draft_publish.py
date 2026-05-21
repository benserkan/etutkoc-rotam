"""task is_draft + published_at — Stage 15 draft/publish workflow

Revision ID: m1h7k0i1j00e
Revises: l0g6j9h0i99d
Create Date: 2026-05-12 17:00:00.000000

Öğretmen haftalık programı serbestçe hazırlayabilsin diye taslak/yayınla
ayrımı. is_draft=True görevler yalnızca öğretmen tarafında görünür;
False olunca öğrenci paneline iner ve veliye duyuru için aday olur.

Backfill: tüm mevcut görevler is_draft=False ile başlar (canlı veri
korunsun, regresyon olmasın). published_at server_default ile mevcut
created_at'e set edilmez — NULL bırakılır, yeni yayınlama eyleminde dolar.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m1h7k0i1j00e"
down_revision: Union[str, None] = "l0g6j9h0i99d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        # Default True yeni eklenenler için, ama mevcut satırlar False olsun.
        # Önce nullable ekle, sonra backfill, sonra NOT NULL'a çek.
        batch_op.add_column(
            sa.Column("is_draft", sa.Boolean(), nullable=True, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True)
        )

    # Backfill: tüm mevcut görevler canlı (is_draft=False)
    op.execute("UPDATE tasks SET is_draft = 0 WHERE is_draft IS NULL")

    # NOT NULL'a çek — server_default kalıyor, yeni satırlar False ile gelir
    # AMA application layer (create_task) bunu override edip True yapacak
    # uygun günler için (yarın+).
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.alter_column("is_draft", existing_type=sa.Boolean(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("published_at")
        batch_op.drop_column("is_draft")
