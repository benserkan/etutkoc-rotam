"""institution_quota_overrides

Revision ID: a9v5y8x9y88s
Revises: z8u4x7w8x77r
Create Date: 2026-05-09 23:55:00.000000

Stage 8 — kuota override tablosu (per-kurum manuel limit ayarları).
Plan default'ları kodda (PLAN_QUOTAS); bu tablo sadece exception'ları tutar.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a9v5y8x9y88s"
down_revision: Union[str, None] = "z8u4x7w8x77r"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "institution_quota_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("quota_key", sa.String(length=40), nullable=False),
        sa.Column("override_value", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE",
            name="fk_quota_override_institution",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "institution_id", "quota_key",
            name="uq_quota_override_inst_key",
        ),
    )
    with op.batch_alter_table("institution_quota_overrides") as batch:
        batch.create_index("ix_quota_override_institution", ["institution_id"])


def downgrade() -> None:
    op.drop_table("institution_quota_overrides")
