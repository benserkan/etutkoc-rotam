"""student_weekly_email cron schedule — günlük (06:00 UTC)

Revision ID: o5p8s1u2u55o
Revises: n4o7r0t1t44n
Create Date: 2026-08-12 00:00:00.000000

Öğrenci e-posta fallback'i cron seed (2026-08-12 kullanıcı kararı):
- job_key='student_weekly_email'
- Her gün 06:00 UTC (09:00 TR) — kayıtlı mobil cihazı OLMAYAN aktif
  öğrencilere haftalık gelişim özeti e-postası. 6 günlük comm_log dedup'u
  sayesinde fiilen öğrenci başına haftada 1. Veli bağı ARANMAZ — velisiz
  öğrenci de alır (Hatice vakası: kiracıda veli yoktu, hiçbir bildirim
  doğmuyordu).
- Sabah saati bilinçli: gece 23:55 weekly_backstop'a bağlansaydı öğrenciye
  gece yarısı mail düşerdi.
- İdempotent INSERT.

NOT: enabled BOOLEAN kolonuna bind param (:e=True) — Postgres'te literal 1
DatatypeMismatch verir (cron seed dersi).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o5p8s1u2u55o"
down_revision: Union[str, None] = "n4o7r0t1t44n"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT 1 FROM cron_schedules WHERE job_key = :k"),
        {"k": "student_weekly_email"},
    ).first()
    if existing is not None:
        return
    bind.execute(
        sa.text(
            "INSERT INTO cron_schedules "
            "(job_key, description, hour, minute, day_of_week, enabled) "
            "VALUES (:k, :d, :h, :m, :w, :e)"
        ),
        {
            "k": "student_weekly_email",
            "d": "Günlük 06:00 UTC — cihazsız öğrencilere haftalık gelişim özeti e-postası (6g dedup)",
            "h": 6,
            "m": 0,
            "w": None,  # her gün (dedup haftada 1'e indirir)
            "e": True,  # bind param — Postgres bool
        },
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM cron_schedules WHERE job_key = :k"),
        {"k": "student_weekly_email"},
    )
