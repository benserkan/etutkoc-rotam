"""admin_weekly_digests — kurum yöneticisi haftalık özet arşivi

Revision ID: v4q0u3s4t33n
Revises: u3p9t2r3s22m
Create Date: 2026-05-09 20:00:00.000000

Stage 4 — Otomatik haftalık yönetici e-posta:
- Tablo: admin_weekly_digests
- (institution_id, week_start_date) UNIQUE → idempotency
- Cron Pazartesi 09:00 UTC çalışır, her aktif kuruma 1 satır
- payload_json: snapshot (UI arşivde tekrar gösterim için)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v4q0u3s4t33n"
down_revision: Union[str, None] = "u3p9t2r3s22m"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_weekly_digests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("week_start_date", sa.Date(), nullable=False),
        sa.Column("week_end_date", sa.Date(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("recipient_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recipient_emails", sa.Text(), nullable=True),
        sa.Column("send_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE",
            name="fk_admin_digest_institution",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "institution_id", "week_start_date",
            name="uq_admin_digest_inst_week",
        ),
    )
    with op.batch_alter_table("admin_weekly_digests") as batch:
        batch.create_index("ix_admin_digests_institution_id", ["institution_id"])


def downgrade() -> None:
    op.drop_table("admin_weekly_digests")
