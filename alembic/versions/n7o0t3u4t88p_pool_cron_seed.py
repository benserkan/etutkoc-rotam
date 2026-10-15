"""Havuz modu cron kayıtları (Adım 3, 2026-10-12): gün sonu kap kapanışı + hatırlatmalar.

  · pool_daily_close — günlük 00:15 UTC (03:15 TR): dünün kapları havuza döner (K34)
  · pool_reminders   — 30 dk'da bir: sabah "havuzdan ne alıyorsun" (olağan başlama saati
                       sonrası, şube ders programıyla) + akşam 21:00 "işaretledin mi" (K37)
Yalnız cron_schedules satırı; additive, downgrade'li. enabled BOOLEAN → bool bind (:e=True).

Revision ID: n7o0t3u4t88p
Revises: n6o9s2t3s77o
Create Date: 2026-10-12
"""
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n7o0t3u4t88p"
down_revision: Union[str, None] = "n6o9s2t3s77o"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JOBS = [
    ("pool_daily_close", "Havuz modu: dünün kaplarını kapat, yapılmayan kalem havuza döner (günlük 03:15 TR).",
     0, 15, None),
    ("pool_reminders", "Havuz modu: sabah 'havuzdan ne alıyorsun' + akşam 'işaretledin mi' hatırlatmaları (30 dk).",
     0, 0, 30),
]


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(timezone.utc).isoformat()
    for key, desc, h, m, iv in _JOBS:
        exists = bind.execute(sa.text("SELECT 1 FROM cron_schedules WHERE job_key = :k"), {"k": key}).first()
        if exists is not None:
            continue
        bind.execute(sa.text(
            "INSERT INTO cron_schedules "
            "(job_key, description, hour, minute, day_of_week, interval_minutes, enabled, created_at, updated_at) "
            "VALUES (:k, :d, :h, :m, :dow, :iv, :e, :ts, :ts)"
        ).bindparams(k=key, d=desc, h=h, m=m, dow=None, iv=iv, e=True, ts=now))


def downgrade() -> None:
    bind = op.get_bind()
    for key, *_ in _JOBS:
        bind.execute(sa.text("DELETE FROM cron_schedules WHERE job_key = :k"), {"k": key})
