"""interval_minutes + 5 güvenlik kamerası cron seed (Katman 11.J)

Revision ID: z4v1y3x4w22r
Revises: y3u0x2w3v11q
Create Date: 2026-05-16 09:00:00.000000

  1) cron_schedules tablosuna interval_minutes (nullable) ekle
  2) 5 yeni cron job satırı seed et:
     - security_alarm_evaluate    (her 5 dk)
     - abuse_scan                 (her 60 dk)
     - error_event_retention      (her gün 03:30)
     - slow_request_retention     (her gün 03:35)
     - security_integrity_scan    (her gün 04:00)
"""
from typing import Sequence, Union
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision: str = "z4v1y3x4w22r"
down_revision: Union[str, None] = "y3u0x2w3v11q"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) interval_minutes kolonu
    with op.batch_alter_table("cron_schedules") as batch:
        batch.add_column(sa.Column("interval_minutes", sa.Integer(), nullable=True))

    # 2) Seed 5 yeni cron
    now = datetime.now(timezone.utc).isoformat()
    seeds = [
        # (job_key, description, hour, minute, day_of_week, interval_minutes)
        ("security_alarm_evaluate",
         "Güvenlik alarm motorunu her 5 dakikada bir çalıştır.",
         0, 0, None, 5),
        ("abuse_scan",
         "Saatlik abuse tespiti taraması (mass invite/notify/multi-account/unsubscribe).",
         0, 0, None, 60),
        ("error_event_retention",
         "30 günden eski resolved hata gruplarını sil.",
         3, 30, None, None),
        ("slow_request_retention",
         "7 günden eski yavaş request log kayıtlarını sil.",
         3, 35, None, None),
        ("security_integrity_scan",
         "Günlük veri bütünlüğü taraması (orphan + KVKK SLA).",
         4, 0, None, None),
    ]
    for job_key, desc, hour, minute, dow, interval in seeds:
        op.execute(sa.text(
            "INSERT INTO cron_schedules "
            "(job_key, description, hour, minute, day_of_week, "
            " interval_minutes, enabled, created_at, updated_at) "
            "VALUES (:k, :d, :h, :m, :dow, :iv, 1, :ts, :ts)"
        ).bindparams(
            k=job_key, d=desc, h=hour, m=minute, dow=dow, iv=interval, ts=now
        ))


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM cron_schedules WHERE job_key IN ("
        "'security_alarm_evaluate', 'abuse_scan', "
        "'error_event_retention', 'slow_request_retention', "
        "'security_integrity_scan')"
    ))
    with op.batch_alter_table("cron_schedules") as batch:
        batch.drop_column("interval_minutes")
