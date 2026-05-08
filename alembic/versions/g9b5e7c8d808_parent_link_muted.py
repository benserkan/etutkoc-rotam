"""parent_student_links.muted — çocuk başına bildirim sustur

Revision ID: g9b5e7c8d808
Revises: f8a4d5b6c707
Create Date: 2026-05-02 14:00:00.000000

Sprint 10 — Veli ayarlar UI: bir veli çoğul çocuk için tek tek bildirim
yayınını kapatabilsin. Default=False (eskisi gibi açık).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g9b5e7c8d808"
down_revision: Union[str, None] = "f8a4d5b6c707"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("parent_student_links") as batch:
        batch.add_column(
            sa.Column("muted", sa.Boolean(), nullable=False, server_default=sa.text("0"))
        )


def downgrade() -> None:
    with op.batch_alter_table("parent_student_links") as batch:
        batch.drop_column("muted")
