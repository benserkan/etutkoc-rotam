"""student_books.archived_at — kitap arşivi (P4, 2026-09-04)

Additive + nullable. Soft arşiv: kayıt SİLİNMEZ, görev geçmişi ve sayaçlar
korunur; yalnız ileriye dönük yüzeylerde (kaynak seçimi, kapasite, öneri,
müfredat kapsama) gizlenir.

Revision ID: t5u8x1y2x66t
Revises: s3t6w9x0w55s
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "t5u8x1y2x66t"
down_revision = "s3t6w9x0w55s"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "student_books",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_student_books_archived_at", "student_books", ["archived_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_student_books_archived_at", table_name="student_books")
    op.drop_column("student_books", "archived_at")
