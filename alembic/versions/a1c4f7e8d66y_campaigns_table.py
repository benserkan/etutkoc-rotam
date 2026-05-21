"""Campaigns + campaign_recipients tablosu (Sprint E.1 — Toplu Kampanya).

Revision ID: a1c4f7e8d66y
Revises: f0c3e5d6e55x
Create Date: 2026-05-16 19:00:00.000000

Yeni tablolar:
  - campaigns: segment + variant_a (+ opsiyonel variant_b A/B testi) + status
  - campaign_recipients: kampanya × kurum × variant + üretilen offer_id + funnel status
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1c4f7e8d66y"
down_revision: Union[str, None] = "f0c3e5d6e55x"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column(
            "segment",
            sa.Enum(
                "free_plan", "trial_ending_7d", "paused_30d", "champion",
                "paying_at_risk", "never_logged_in", "custom_plan",
                name="campaignsegment",
            ),
            nullable=False,
        ),
        sa.Column("segment_filter_plan", sa.String(length=32), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft", "running", "paused", "completed", "cancelled",
                name="campaignstatus",
            ),
            nullable=False, server_default="draft",
        ),

        # Varyant A
        sa.Column("variant_a_kind", sa.String(length=32), nullable=False),
        sa.Column("variant_a_title", sa.String(length=255), nullable=False),
        sa.Column("variant_a_value", sa.Numeric(10, 2), nullable=True),
        sa.Column("variant_a_duration_months", sa.Integer(), nullable=True),
        sa.Column("variant_a_new_plan", sa.String(length=32), nullable=True),
        sa.Column("variant_a_public_message", sa.Text(), nullable=True),

        # Varyant B (opsiyonel)
        sa.Column("has_variant_b", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column("variant_b_kind", sa.String(length=32), nullable=True),
        sa.Column("variant_b_title", sa.String(length=255), nullable=True),
        sa.Column("variant_b_value", sa.Numeric(10, 2), nullable=True),
        sa.Column("variant_b_duration_months", sa.Integer(), nullable=True),
        sa.Column("variant_b_new_plan", sa.String(length=32), nullable=True),
        sa.Column("variant_b_public_message", sa.Text(), nullable=True),

        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("offer_expires_in_days", sa.Integer(), nullable=False,
                  server_default="14"),

        sa.Column(
            "created_by_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL",
                          name="fk_campaigns_created_by"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_campaigns_status", "campaigns", ["status"])
    op.create_index("ix_campaigns_segment", "campaigns", ["segment"])

    op.create_table(
        "campaign_recipients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campaign_id", sa.Integer(),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE",
                          name="fk_camp_rec_campaign"),
            nullable=False,
        ),
        sa.Column(
            "institution_id", sa.Integer(),
            sa.ForeignKey("institutions.id", ondelete="CASCADE",
                          name="fk_camp_rec_institution"),
            nullable=False,
        ),
        sa.Column("variant", sa.String(length=1), nullable=False,
                  server_default="A"),
        sa.Column(
            "offer_id", sa.Integer(),
            sa.ForeignKey("offers.id", ondelete="SET NULL",
                          name="fk_camp_rec_offer"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "targeted", "sent", "accepted", "declined",
                "expired", "bounced",
                name="recipientstatus",
            ),
            nullable=False, server_default="targeted",
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_campaign_recipients_campaign",
                    "campaign_recipients", ["campaign_id"])
    op.create_index("ix_campaign_recipients_inst",
                    "campaign_recipients", ["institution_id"])
    op.create_index("ix_campaign_recipients_status",
                    "campaign_recipients", ["campaign_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_campaign_recipients_status",
                  table_name="campaign_recipients")
    op.drop_index("ix_campaign_recipients_inst",
                  table_name="campaign_recipients")
    op.drop_index("ix_campaign_recipients_campaign",
                  table_name="campaign_recipients")
    op.drop_table("campaign_recipients")
    op.drop_index("ix_campaigns_segment", table_name="campaigns")
    op.drop_index("ix_campaigns_status", table_name="campaigns")
    op.drop_table("campaigns")
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        sa.Enum(name="campaignsegment").drop(bind, checkfirst=True)
        sa.Enum(name="campaignstatus").drop(bind, checkfirst=True)
        sa.Enum(name="recipientstatus").drop(bind, checkfirst=True)
