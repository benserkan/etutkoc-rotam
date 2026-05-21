"""Health score snapshots (Sprint F.1 — Sağlık Skoru 2.0).

Revision ID: b2d5g8f9e77z
Revises: a1c4f7e8d66y
Create Date: 2026-05-16 22:00:00.000000

Yeni tablo:
  - health_score_snapshots: kurum × gün başına 1 sağlık skoru snapshot
    (user-facing 0-100, yüksek=sağlıklı). 7 günlük düşüş tetikleyici hesabı
    bu tablodan yapılır.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2d5g8f9e77z"
down_revision: Union[str, None] = "a1c4f7e8d66y"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "health_score_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "institution_id", sa.Integer(),
            sa.ForeignKey("institutions.id", ondelete="CASCADE",
                          name="fk_health_snap_inst"),
            nullable=False,
        ),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("band", sa.String(length=20), nullable=False),
        sa.Column("components_json", sa.Text(), nullable=True),
        sa.Column("active_teacher_count", sa.Integer(),
                  nullable=False, server_default="0"),
        sa.Column("active_student_count", sa.Integer(),
                  nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "institution_id", "snapshot_date",
            name="uq_health_snapshot_inst_date",
        ),
    )
    op.create_index(
        "ix_health_snapshot_inst_date",
        "health_score_snapshots",
        ["institution_id", "snapshot_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_health_snapshot_inst_date",
                  table_name="health_score_snapshots")
    op.drop_table("health_score_snapshots")
