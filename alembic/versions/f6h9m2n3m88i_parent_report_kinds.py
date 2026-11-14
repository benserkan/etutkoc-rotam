"""Veli rapor bağlantıları: gelişim + haftalık rapor türleri (2026-11-14).

Revision ID: f6h9m2n3m88i
Revises: e5g8l1m2l77h
"""
from alembic import op
import sqlalchemy as sa

revision = "f6h9m2n3m88i"
down_revision = "e5g8l1m2l77h"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("exam_parent_reports") as b:
        b.add_column(sa.Column("kind", sa.String(16), server_default="exam", nullable=False))
        b.add_column(sa.Column("week_start", sa.Date(), nullable=True))
        b.add_column(sa.Column("series", sa.String(64), nullable=True))
        b.alter_column("exam_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM exam_parent_reports WHERE exam_id IS NULL"))
    with op.batch_alter_table("exam_parent_reports") as b:
        b.alter_column("exam_id", existing_type=sa.Integer(), nullable=False)
        b.drop_column("series")
        b.drop_column("week_start")
        b.drop_column("kind")
