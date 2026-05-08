"""audit_cleanup cron schedule — 180 günden eski audit_logs satırlarını temizle

Revision ID: s1n7r0p1q00k
Revises: r0m6q8n9o99j
Create Date: 2026-05-09 14:00:00.000000

Audit polish sprint:
- audit_cleanup job_key ile tek satır seed
- Çalışma: her gün 03:00 UTC (TR 06:00) — düşük trafik penceresi
- Idempotent: zaten varsa eklenmez

Job kodu app/services/cron_jobs.py::audit_cleanup'ta. AUDIT_LOG_RETENTION_DAYS
sabiti orada — değiştirilirse buradaki seed satırı yeniden çalıştırılmaz
(satır zaten var). Operatör değişirse yeni migration ile yapsın veya UI'dan.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "s1n7r0p1q00k"
down_revision: Union[str, None] = "r0m6q8n9o99j"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # Idempotent: zaten varsa atla (test/dev'de migrate-rollback-migrate dayanıklılığı)
    existing = bind.execute(
        sa.text("SELECT 1 FROM cron_schedules WHERE job_key = :k"),
        {"k": "audit_cleanup"},
    ).first()
    if existing is not None:
        return
    bind.execute(
        sa.text(
            "INSERT INTO cron_schedules "
            "(job_key, description, hour, minute, day_of_week, enabled) "
            "VALUES (:k, :d, :h, :m, :w, 1)"
        ),
        {
            "k": "audit_cleanup",
            "d": "Her gün 03:00 UTC — 180+ günlük audit kayıtlarını temizler",
            "h": 3,
            "m": 0,
            "w": None,
        },
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM cron_schedules WHERE job_key = :k"),
        {"k": "audit_cleanup"},
    )
