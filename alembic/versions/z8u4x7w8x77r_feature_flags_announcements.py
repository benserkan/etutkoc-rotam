"""feature_flags + feature_flag_overrides + system_announcements

Revision ID: z8u4x7w8x77r
Revises: y7t3w6v7w66q
Create Date: 2026-05-09 23:30:00.000000

Stage 7 — sistem yönetim araçları:
- feature_flags (key UNIQUE + global default)
- feature_flag_overrides (per-kurum override, UNIQUE pair)
- system_announcements (severity + audience + zaman aralığı)
- 4 başlangıç flag seed: ai_book_template, parent_notifications_email,
  parent_notifications_whatsapp, weekly_admin_digest
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "z8u4x7w8x77r"
down_revision: Union[str, None] = "y7t3w6v7w66q"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) feature_flags
    op.create_table(
        "feature_flags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "enabled_globally", sa.Boolean(), nullable=False, server_default=sa.text("1"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_feature_flag_key"),
    )

    # 2) feature_flag_overrides
    op.create_table(
        "feature_flag_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("feature_flag_id", sa.Integer(), nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
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
            ["feature_flag_id"], ["feature_flags.id"], ondelete="CASCADE",
            name="fk_ffo_flag",
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE",
            name="fk_ffo_institution",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "feature_flag_id", "institution_id",
            name="uq_feature_flag_override_pair",
        ),
    )
    with op.batch_alter_table("feature_flag_overrides") as batch:
        batch.create_index("ix_ffo_flag", ["feature_flag_id"])
        batch.create_index("ix_ffo_institution", ["institution_id"])

    # 3) system_announcements
    op.create_table(
        "system_announcements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="info"),
        sa.Column("audience", sa.String(length=32), nullable=False, server_default="all"),
        sa.Column(
            "starts_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "dismissible", sa.Boolean(), nullable=False, server_default=sa.text("1"),
        ),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], ondelete="SET NULL",
            name="fk_announcement_creator",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 4) Başlangıç feature flag seed (4 adet)
    bind = op.get_bind()
    seeds = [
        ("ai_book_template", "AI ile kitap ünite şablonu önerisi (Claude Haiku)"),
        ("parent_notifications_email", "Veliye e-posta bildirimleri"),
        ("parent_notifications_whatsapp", "Veliye WhatsApp bildirimleri"),
        ("weekly_admin_digest", "Haftalık yönetici özet e-postası (Pazartesi 09:00 UTC)"),
    ]
    for key, desc in seeds:
        bind.execute(
            sa.text(
                "INSERT INTO feature_flags (key, description, enabled_globally) "
                "VALUES (:k, :d, 1)"
            ),
            {"k": key, "d": desc},
        )


def downgrade() -> None:
    op.drop_table("system_announcements")
    op.drop_table("feature_flag_overrides")
    op.drop_table("feature_flags")
