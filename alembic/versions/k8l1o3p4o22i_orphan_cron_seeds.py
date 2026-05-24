"""Kopuk-cron düzeltmeleri — health_snapshot_daily + offers_expire schedule seed

Revision ID: k8l1o3p4o22i
Revises: j7k0n2o3n11h
Create Date: 2026-05-24 18:00:00.000000

Kopuk-servis denetiminde bulunan 2 cron, JOB_REGISTRY'de olmasına rağmen hiç
CronSchedule satırı olmadığı için çalışmıyordu:
- health_snapshot_daily: günlük sağlık skoru snapshot'ı (trend/churn geçmişi).
  Snapshot'lar 2026-05-16'da donmuştu → günlük 04:30 UTC.
- offers_expire: süresi dolmuş SENT teklifleri EXPIRED'a çek (lazy expire'ı
  tamamlar; açılmamış teklifler sayımı şişirmesin) → günlük 02:15 UTC.

İdempotent INSERT (her job_key için SELECT 1 kontrolü). Additive, downgrade'li.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k8l1o3p4o22i"
down_revision: Union[str, None] = "j7k0n2o3n11h"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SEEDS = [
    {
        "k": "health_snapshot_daily",
        "d": "Günlük 04:30 UTC — tüm aktif owner için sağlık skoru snapshot'ı (trend/churn geçmişi)",
        "h": 4, "m": 30, "w": None,
    },
    {
        "k": "offers_expire",
        "d": "Günlük 02:15 UTC — süresi dolmuş SENT teklifleri EXPIRED yap",
        "h": 2, "m": 15, "w": None,
    },
]


def upgrade() -> None:
    bind = op.get_bind()
    for s in _SEEDS:
        existing = bind.execute(
            sa.text("SELECT 1 FROM cron_schedules WHERE job_key = :k"), {"k": s["k"]}
        ).first()
        if existing is not None:
            continue
        bind.execute(
            sa.text(
                "INSERT INTO cron_schedules "
                "(job_key, description, hour, minute, day_of_week, enabled) "
                "VALUES (:k, :d, :h, :m, :w, 1)"
            ),
            s,
        )


def downgrade() -> None:
    bind = op.get_bind()
    for s in _SEEDS:
        bind.execute(
            sa.text("DELETE FROM cron_schedules WHERE job_key = :k"), {"k": s["k"]}
        )
