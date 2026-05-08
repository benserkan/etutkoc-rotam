"""cron schedules — admin-editable bildirim zamanlamaları

Revision ID: e7b3c4d5f606
Revises: d5e2f3a4b505
Create Date: 2026-05-05 13:00:00.000000

Sprint 5 — cron job'lar:
- cron_schedules tablosu: job_key, hour, minute, day_of_week (NULL=her gün),
  enabled, last_run_at, last_status, last_error
- Default 4 satır seed: daily_summary (21:00), weekly_backstop (23:55),
  drop_alert (Pzt 06:00), empty_day_check (21:00)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7b3c4d5f606"
down_revision: Union[str, None] = "d5e2f3a4b505"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_SCHEDULES = [
    # (job_key, hour, minute, day_of_week, description)
    ("daily_summary",     21, 0,  None, "Her akşam 21:00 — günlük özet + boş gün kontrolü"),
    ("weekly_backstop",   23, 55, None, "Her gece 23:55 — haftalık döngü-son backstop"),
    ("drop_alert",        6,  0,  0,    "Pazartesi 06:00 — düşüş alarmı (geçen haftaya göre)"),
]


def upgrade() -> None:
    op.create_table(
        "cron_schedules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_key", sa.String(length=40), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("hour", sa.Integer(), nullable=False),
        sa.Column("minute", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("day_of_week", sa.Integer(), nullable=True),  # 0=Pzt..6=Paz, NULL=her gün
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=20), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_key", name="uq_cron_job_key"),
    )

    # Seed default schedules
    bind = op.get_bind()
    for job_key, hour, minute, dow, desc in DEFAULT_SCHEDULES:
        bind.execute(
            sa.text(
                "INSERT INTO cron_schedules (job_key, description, hour, minute, day_of_week, enabled) "
                "VALUES (:k, :d, :h, :m, :w, 1)"
            ),
            {"k": job_key, "d": desc, "h": hour, "m": minute, "w": dow},
        )


def downgrade() -> None:
    op.drop_table("cron_schedules")
