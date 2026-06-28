"""release_dead_reservations cron schedule — günlük (04:10 UTC)

Revision ID: t4u7x0y1x33t
Revises: s2t5v8w9v11s
Create Date: 2026-06-28 00:00:00.000000

Ölü rezerv telafisi cron seed:
- job_key='release_dead_reservations'
- Her gün 04:10 UTC — rezervli öğrencilerde geçmiş hafta yapılmamış görevlerin
  'ölü rezervini' otomatik serbest bırakır (koç yeni program/görev-ekle yapmasa
  bile yaz/program-arası boşlukta rezerv birikmesin). reconcile idempotent +
  release-only; cari hafta + aktif program rezervleri KORUNUR.
- İdempotent INSERT.

NOT: enabled BOOLEAN kolonuna literal 1 yerine bind param (:e=True) yazılır —
Postgres'te literal 1 DatatypeMismatch verir (cron seed dersi, QA-1).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "t4u7x0y1x33t"
down_revision: Union[str, None] = "s2t5v8w9v11s"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT 1 FROM cron_schedules WHERE job_key = :k"),
        {"k": "release_dead_reservations"},
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
            "k": "release_dead_reservations",
            "d": "Günlük 04:10 UTC — ölü rezervi (geçmiş hafta, yapılmamış görev) serbest bırak",
            "h": 4,
            "m": 10,
            "w": None,  # her gün
            "e": True,  # bind param — Postgres bool (literal 1 DatatypeMismatch verir)
        },
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM cron_schedules WHERE job_key = :k"),
        {"k": "release_dead_reservations"},
    )
