"""campaign_links — WhatsApp gruplarına paylaşılabilen public markalı kampanya linki

Kişiye özel olmayan, tekrar kullanılabilir landing (1:çok). Ziyaretçi ad+telefon
bırakır → SalesProspect (lead) + ContactRequest → mevcut onboard akışı. Additive,
downgrade'li.

Revision ID: r1s4u7v8u00r
Revises: q0r3u6v7u99p
Create Date: 2026-06-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r1s4u7v8u00r"
down_revision: Union[str, None] = "q0r3u6v7u99p"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "campaign_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("audience", sa.String(length=16), nullable=False, server_default="coach"),
        sa.Column("plan_code", sa.String(length=50), nullable=False),
        sa.Column("cycle", sa.String(length=16), nullable=False, server_default="monthly"),
        sa.Column("amount", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lead_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_admin_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("token", name="uq_campaign_link_token"),
    )
    op.create_index("ix_campaign_link_token", "campaign_links", ["token"])
    op.create_index("ix_campaign_link_status", "campaign_links", ["status"])


def downgrade() -> None:
    op.drop_index("ix_campaign_link_status", table_name="campaign_links")
    op.drop_index("ix_campaign_link_token", table_name="campaign_links")
    op.drop_table("campaign_links")
