"""Deneme sonuç girişi (D2, 2026-10-20).

`task_book_items` + `duration_minutes` (öğrencinin girdiği süre, isteğe bağlı) +
`result_reminded_at` (sonucu girilmemiş deneme için hatırlatma bir kez gider).
Cron `deneme_result_reminders`: günlük 16:00 UTC (19:00 TR) — çözülmüş ama 2+ gündür
sonucu girilmemiş denemeler için öğrenciye push. Additive, downgrade'li.

Revision ID: r2t5y8z9y44u
Revises: q1s4x7y8x33t
Create Date: 2026-10-20
"""
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r2t5y8z9y44u"
down_revision: Union[str, None] = "q1s4x7y8x33t"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JOB = ("deneme_result_reminders",
        "Sonucu girilmemiş denemeler için öğrenciye hatırlatma (D2)", 16, 0, None)


def upgrade() -> None:
    with op.batch_alter_table("task_book_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("duration_minutes", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("result_reminded_at", sa.DateTime(timezone=True), nullable=True))
    bind = op.get_bind()
    key, desc, h, m, iv = _JOB
    exists = bind.execute(sa.text("SELECT 1 FROM cron_schedules WHERE job_key = :k"), {"k": key}).first()
    if exists is None:
        now = datetime.now(timezone.utc).isoformat()
        bind.execute(sa.text(
            "INSERT INTO cron_schedules "
            "(job_key, description, hour, minute, day_of_week, interval_minutes, enabled, created_at, updated_at) "
            "VALUES (:k, :d, :h, :m, :dow, :iv, :e, :ts, :ts)"
        ).bindparams(k=key, d=desc, h=h, m=m, dow=None, iv=iv, e=True, ts=now))


def downgrade() -> None:
    op.get_bind().execute(sa.text("DELETE FROM cron_schedules WHERE job_key = :k"), {"k": _JOB[0]})
    with op.batch_alter_table("task_book_items", schema=None) as batch_op:
        batch_op.drop_column("result_reminded_at")
        batch_op.drop_column("duration_minutes")
