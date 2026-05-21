"""dunning_send_reminders cron seed (Sprint C — Aksiyon Merkezi + Dunning).

Revision ID: e9b2d4c5d44w
Revises: d8a1c3b4c33v
Create Date: 2026-05-16 15:00:00.000000

Günlük 09:00 UTC (TR 12:00) ödeme hatırlatma zinciri tetikleyici cron.
D-7, D-3, D-1, D+1, D+3, D+7 aşamaları arasında uygun olanı her fatura için
otomatik gönderir.
"""
from typing import Sequence, Union
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision: str = "e9b2d4c5d44w"
down_revision: Union[str, None] = "d8a1c3b4c33v"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    now = datetime.now(timezone.utc).isoformat()
    op.execute(sa.text(
        "INSERT INTO cron_schedules "
        "(job_key, description, hour, minute, day_of_week, "
        " interval_minutes, enabled, created_at, updated_at) "
        "VALUES (:k, :d, :h, :m, :dow, :iv, 1, :ts, :ts)"
    ).bindparams(
        k="dunning_send_reminders",
        d=("Ödeme hatırlatma zinciri (D-7..D+7). Her fatura için uygun aşamayı "
           "günde bir kez tetikler."),
        h=9, m=0, dow=None, iv=None, ts=now,
    ))


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM cron_schedules WHERE job_key = 'dunning_send_reminders'"
    ))
