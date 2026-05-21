"""abuse_signals — kötüye kullanım sinyalleri (Katman 11.C)

Revision ID: w1s8v0u1t99o
Revises: v0r7u9t0s88n
Create Date: 2026-05-15 16:00:00.000000

Periyodik abuse tespit servisinin ürettiği sinyaller. Süper admin panosunda
listelenir; resolve edilince kapanır. Dedup için 24h pencere.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "w1s8v0u1t99o"
down_revision: Union[str, None] = "v0r7u9t0s88n"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "abuse_signals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=10), nullable=False, server_default="warn"),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("institutions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "resolved_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolution_note", sa.String(length=500), nullable=True),
    )
    op.create_index("ix_abuse_kind_resolved", "abuse_signals", ["kind", "resolved_at"])
    op.create_index("ix_abuse_actor", "abuse_signals", ["actor_user_id"])
    op.create_index("ix_abuse_tenant", "abuse_signals", ["tenant_id"])
    op.create_index("ix_abuse_detected", "abuse_signals", ["detected_at"])


def downgrade() -> None:
    op.drop_index("ix_abuse_detected", table_name="abuse_signals")
    op.drop_index("ix_abuse_tenant", table_name="abuse_signals")
    op.drop_index("ix_abuse_actor", table_name="abuse_signals")
    op.drop_index("ix_abuse_kind_resolved", table_name="abuse_signals")
    op.drop_table("abuse_signals")
