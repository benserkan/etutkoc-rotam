"""notification dispatch — retry/scheduled_at + unsubscribe token

Revision ID: d5e2f3a4b505
Revises: c4f1d8a3e202
Create Date: 2026-05-05 12:00:00.000000

Sprint 4 — bildirim dispatch altyapısı:
- notification_logs'a `scheduled_at`, `attempts`, `next_attempt_at` (retry/quiet-hours için)
- parent_notification_prefs'e `unsubscribe_token` (UNIQUE) + `unsubscribed_at`
- Mevcut veliler için unsubscribe_token backfill (secrets.token_urlsafe)
"""
from typing import Sequence, Union
import secrets

from alembic import op
import sqlalchemy as sa


revision: str = "d5e2f3a4b505"
down_revision: Union[str, None] = "c4f1d8a3e202"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) notification_logs — retry/schedule alanları
    with op.batch_alter_table("notification_logs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column(
            "attempts", sa.Integer(), nullable=False, server_default="0"
        ))
        batch_op.add_column(sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_notif_dispatch_ready", ["status", "next_attempt_at"], unique=False)

    # 2) parent_notification_prefs — unsubscribe_token + unsubscribed_at
    with op.batch_alter_table("parent_notification_prefs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("unsubscribe_token", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(
            "ix_parent_pref_unsub_token", ["unsubscribe_token"], unique=True
        )

    # 3) Mevcut prefs satırlarına token backfill
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT id FROM parent_notification_prefs WHERE unsubscribe_token IS NULL"
    )).fetchall()
    for (pref_id,) in rows:
        token = secrets.token_urlsafe(48)
        bind.execute(
            sa.text("UPDATE parent_notification_prefs SET unsubscribe_token = :t WHERE id = :id"),
            {"t": token, "id": pref_id},
        )


def downgrade() -> None:
    with op.batch_alter_table("parent_notification_prefs", schema=None) as batch_op:
        batch_op.drop_index("ix_parent_pref_unsub_token")
        batch_op.drop_column("unsubscribed_at")
        batch_op.drop_column("unsubscribe_token")

    with op.batch_alter_table("notification_logs", schema=None) as batch_op:
        batch_op.drop_index("ix_notif_dispatch_ready")
        batch_op.drop_column("next_attempt_at")
        batch_op.drop_column("attempts")
        batch_op.drop_column("scheduled_at")
