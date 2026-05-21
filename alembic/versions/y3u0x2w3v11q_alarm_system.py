"""alarm_rules + alarm_events — eşik tabanlı alarm sistemi (Katman 11.F)

Revision ID: y3u0x2w3v11q
Revises: x2t9w1v2u00p
Create Date: 2026-05-15 18:00:00.000000

Alarm konfigürasyonu (kurallar) + tetiklenen olaylar (history).
4 varsayılan kural seed edilir.
"""
from typing import Sequence, Union
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision: str = "y3u0x2w3v11q"
down_revision: Union[str, None] = "x2t9w1v2u00p"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "alarm_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("threshold", sa.Integer(), nullable=False),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("channels", sa.String(length=60), nullable=False, server_default="email,in_app"),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_value", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_alarm_rule_key", "alarm_rules", ["key"], unique=True)
    op.create_index("ix_alarm_rule_enabled", "alarm_rules", ["enabled"])

    op.create_table(
        "alarm_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rule_key", sa.String(length=60), nullable=False),
        sa.Column("rule_name", sa.String(length=160), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("threshold", sa.Integer(), nullable=False),
        sa.Column("severity", sa.String(length=10), nullable=False, server_default="warn"),
        sa.Column("channels_attempted", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("delivery_status", sa.String(length=60), nullable=False, server_default="pending"),
        sa.Column("details_json", sa.Text(), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "acknowledged_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_alarm_event_rule_time", "alarm_events", ["rule_key", "triggered_at"]
    )
    op.create_index("ix_alarm_event_time", "alarm_events", ["triggered_at"])

    # Seed varsayılan kurallar
    now = datetime.now(timezone.utc).isoformat()
    seeds = [
        ("high_failed_logins", "Yüksek başarısız login",
         "Son 24 saatte başarısız giriş eşiği aşıldı.", 50, 60),
        ("oldest_queued_long", "Kuyrukta uzun süre bekleyen bildirim",
         "En eski queued bildirim eşik dakikasından eski.", 60, 30),
        ("error_groups_open", "Çok açık hata grubu",
         "Resolved olmayan hata grubu eşiği aştı.", 5, 60),
        ("abuse_open", "Açık abuse sinyali",
         "Resolved olmayan abuse sinyali eşiği aştı.", 0, 30),
    ]
    for key, name, desc, threshold, cd in seeds:
        op.execute(sa.text(
            "INSERT INTO alarm_rules "
            "(key, name, description, threshold, cooldown_minutes, enabled, "
            " channels, created_at, updated_at) "
            "VALUES (:k, :n, :d, :t, :cd, 1, 'email,in_app', :ts, :ts)"
        ).bindparams(k=key, n=name, d=desc, t=threshold, cd=cd, ts=now))


def downgrade() -> None:
    op.drop_index("ix_alarm_event_time", table_name="alarm_events")
    op.drop_index("ix_alarm_event_rule_time", table_name="alarm_events")
    op.drop_table("alarm_events")
    op.drop_index("ix_alarm_rule_enabled", table_name="alarm_rules")
    op.drop_index("ix_alarm_rule_key", table_name="alarm_rules")
    op.drop_table("alarm_rules")
